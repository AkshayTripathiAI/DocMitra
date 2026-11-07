"""Document storage and reminder logic, shared by the API and agent tools."""
import uuid
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .agents.ingest import IngestState
from .config import settings
from .extraction.classify import DOC_TYPES
from .extraction.fields import masked_fields
from .models import Document, Reminder


def expiry_status(expiry: date | None, today: date | None = None) -> str:
    """valid | expiring | expired | none"""
    if expiry is None:
        return "none"
    today = today or date.today()
    if expiry < today:
        return "expired"
    if expiry <= today + timedelta(days=settings.reminder_lead_days):
        return "expiring"
    return "valid"


def save_upload(file_bytes: bytes, filename: str) -> Path:
    uploads = settings.storage_path / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    safe = "".join(c for c in Path(filename).name if c.isalnum() or c in "._-") or "upload"
    path = uploads / f"{date.today():%Y%m%d}-{uuid.uuid4().hex[:8]}-{safe}"
    path.write_bytes(file_bytes)
    return path


def create_document(
    session: Session, *, filename: str, mime_type: str, stored_path: Path, result: IngestState
) -> Document:
    expiry = date.fromisoformat(result["expiry_date"]) if result.get("expiry_date") else None
    doc = Document(
        filename=filename,
        mime_type=mime_type,
        stored_path=str(stored_path),
        doc_type=result.get("doc_type", "UNKNOWN"),
        holder_name=result.get("holder_name"),
        expiry_date=expiry,
        ocr_text=result.get("ocr_text", ""),
        ocr_provider=result.get("ocr_provider", "none"),
        fields=result.get("fields", []),
        quality=result.get("quality") or {},
        notes=result.get("notes", []),
    )
    if expiry:
        doc.reminders.append(expiry_reminder(doc.doc_type, expiry))
    session.add(doc)
    session.commit()
    return doc


def expiry_reminder(doc_type: str, expiry: date) -> Reminder:
    label = DOC_TYPES.get(doc_type, "Document")
    due = max(expiry - timedelta(days=settings.reminder_lead_days), date.today())
    return Reminder(title=f"Renew {label} (expires {expiry:%d %b %Y})", due_date=due)


def list_documents(session: Session) -> list[Document]:
    return list(session.scalars(select(Document).order_by(Document.created_at.desc())))


def document_summary(doc: Document) -> dict:
    """Safe-to-share view: sensitive values masked, no OCR text."""
    return {
        "id": doc.id,
        "doc_type": doc.doc_type,
        "doc_label": DOC_TYPES.get(doc.doc_type, doc.doc_type),
        "holder_name": doc.holder_name,
        "expiry_date": doc.expiry_date.isoformat() if doc.expiry_date else None,
        "status": expiry_status(doc.expiry_date),
        "fields": masked_fields(doc.fields or []),
        "notes": doc.notes or [],
    }
