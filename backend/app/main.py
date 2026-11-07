"""DocMitra API."""
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import services
from .agents import assistant
from .agents.ingest import run_ingest
from .config import settings
from .db import SessionLocal, get_session, init_db
from .demo import seed_demo
from .extraction.classify import DOC_TYPES
from .extraction.matching import compare_names
from .models import Document, Reminder

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "application/pdf"}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    if settings.demo_mode:
        with SessionLocal() as session:
            seed_demo(session)
    yield


app = FastAPI(title="DocMitra API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _document_out(doc: Document) -> dict:
    return {
        **services.document_summary(doc),
        "filename": doc.filename,
        "quality": doc.quality,
        "ocr_provider": doc.ocr_provider,
        "created_at": doc.created_at.isoformat(),
    }


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "llm_model": settings.llm_model,
        "llm_configured": settings.llm_configured,
        "demo_mode": settings.demo_mode,
    }


def _block_in_demo(action: str) -> None:
    if settings.demo_mode:
        raise HTTPException(
            403, f"{action} is turned off in the public demo. Run DocMitra locally to use your own documents."
        )


_chat_hits: dict[str, int] = defaultdict(int)


def _rate_limit_chat(request: Request) -> None:
    limit = settings.chat_rate_limit_per_hour
    if limit <= 0:
        return
    forwarded = request.headers.get("x-forwarded-for", "")
    client = forwarded.split(",")[0].strip() or (request.client.host if request.client else "?")
    key = f"{client}:{int(time.time() // 3600)}"
    if len(_chat_hits) > 10000:
        _chat_hits.clear()
    _chat_hits[key] += 1
    if _chat_hits[key] > limit:
        raise HTTPException(429, "Hourly chat limit reached for this demo. Please try again later.")


@app.get("/api/doc-types")
def doc_types():
    return [{"code": code, "label": label} for code, label in DOC_TYPES.items()]


@app.post("/api/documents", status_code=201)
def upload_document(
    file: UploadFile = File(...),
    doc_type: str | None = Form(None),
    session: Session = Depends(get_session),
):
    _block_in_demo("Uploading")
    mime = file.content_type or ""
    if mime not in ALLOWED_MIME:
        raise HTTPException(415, f"Upload a JPG, PNG, WEBP or PDF (got {mime or 'unknown'}).")
    data = file.file.read(settings.max_upload_bytes + 1)
    if not data:
        raise HTTPException(400, "Empty file.")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, "File is larger than 10 MB.")
    if doc_type and doc_type not in DOC_TYPES:
        raise HTTPException(422, f"Unknown doc_type {doc_type}.")
    result = run_ingest(data, mime, doc_type or None)
    path = services.save_upload(data, file.filename or "upload")
    doc = services.create_document(
        session, filename=file.filename or path.name, mime_type=mime, stored_path=path,
        result=result,
    )
    return _document_out(doc)


@app.get("/api/documents")
def list_documents(session: Session = Depends(get_session)):
    return [_document_out(d) for d in services.list_documents(session)]


def _get_doc(session: Session, document_id: str) -> Document:
    doc = session.get(Document, document_id)
    if doc is None:
        raise HTTPException(404, "Document not found.")
    return doc


@app.get("/api/documents/{document_id}")
def get_document(document_id: str, session: Session = Depends(get_session)):
    return _document_out(_get_doc(session, document_id))


@app.get("/api/documents/{document_id}/file")
def get_document_file(document_id: str, session: Session = Depends(get_session)):
    doc = _get_doc(session, document_id)
    if not doc.stored_path or not Path(doc.stored_path).is_file():
        raise HTTPException(404, "No file stored for this document.")
    return FileResponse(doc.stored_path, media_type=doc.mime_type, filename=doc.filename)


@app.delete("/api/documents/{document_id}", status_code=204)
def delete_document(document_id: str, session: Session = Depends(get_session)):
    _block_in_demo("Deleting documents")
    doc = _get_doc(session, document_id)
    if doc.stored_path:
        Path(doc.stored_path).unlink(missing_ok=True)
    session.delete(doc)
    session.commit()


@app.get("/api/checks/names")
def name_check(session: Session = Depends(get_session)):
    named = [
        (f"{DOC_TYPES.get(d.doc_type, d.doc_type)}", d.holder_name)
        for d in services.list_documents(session)
        if d.holder_name
    ]
    return {"documents": len(named), "pairs": compare_names(named)}


def _reminder_out(r: Reminder) -> dict:
    return {
        "id": r.id,
        "title": r.title,
        "due_date": r.due_date.isoformat(),
        "done": r.done,
        "overdue": not r.done and r.due_date < date.today(),
        "document_id": r.document_id,
    }


@app.get("/api/reminders")
def list_reminders(session: Session = Depends(get_session)):
    rows = session.scalars(select(Reminder).order_by(Reminder.done, Reminder.due_date))
    return [_reminder_out(r) for r in rows]


class ReminderPatch(BaseModel):
    done: bool


@app.patch("/api/reminders/{reminder_id}")
def update_reminder(reminder_id: str, body: ReminderPatch, session: Session = Depends(get_session)):
    reminder = session.get(Reminder, reminder_id)
    if reminder is None:
        raise HTTPException(404, "Reminder not found.")
    reminder.done = body.done
    session.commit()
    return _reminder_out(reminder)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    thread_id: str = Field(default="default", max_length=64)


@app.post("/api/chat")
def chat(body: ChatIn, request: Request):
    _rate_limit_chat(request)
    try:
        return assistant.chat(body.message, body.thread_id)
    except (assistant.LLMNotConfigured, assistant.AssistantUnavailable) as exc:
        raise HTTPException(503, str(exc)) from exc
