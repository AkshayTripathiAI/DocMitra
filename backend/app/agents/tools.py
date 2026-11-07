"""Tools the assistant agent can call.

Everything returned here goes to the LLM, so it only ever uses the
masked document summary, never raw OCR text or full ID numbers.
"""
from datetime import date, timedelta

from langchain_core.tools import tool
from sqlalchemy import select

from .. import services
from ..db import SessionLocal
from ..extraction.classify import DOC_TYPES
from ..extraction.matching import compare_names
from ..models import Document, Reminder
from .procedures import PROCEDURES, find_procedure


@tool
def list_my_documents() -> list[dict]:
    """List every document the user has uploaded: type, holder name, expiry date and
    status (valid / expiring / expired / none). Call this first to see what exists."""
    with SessionLocal() as s:
        return [
            {k: v for k, v in services.document_summary(d).items() if k not in ("fields", "notes")}
            for d in services.list_documents(s)
        ]


@tool
def get_document_details(document_id: str) -> dict:
    """Extracted fields of one document (ID numbers are masked)."""
    with SessionLocal() as s:
        doc = s.get(Document, document_id)
        if doc is None:
            return {"error": f"No document with id {document_id}"}
        return services.document_summary(doc)


@tool
def find_expiring_documents(within_days: int = 60) -> list[dict]:
    """Documents that are already expired or expire within `within_days` days."""
    cutoff = date.today() + timedelta(days=within_days)
    with SessionLocal() as s:
        docs = s.scalars(select(Document).where(Document.expiry_date.is_not(None)))
        return [
            {
                "id": d.id,
                "doc_label": DOC_TYPES.get(d.doc_type, d.doc_type),
                "expiry_date": d.expiry_date.isoformat(),
                "days_left": (d.expiry_date - date.today()).days,
            }
            for d in docs
            if d.expiry_date <= cutoff
        ]


@tool
def check_name_consistency() -> dict:
    """Compare the holder name across all documents. Mismatches (spelling, missing
    middle name) commonly cause rejections in government applications."""
    with SessionLocal() as s:
        named = [
            (DOC_TYPES.get(d.doc_type, d.doc_type), d.holder_name)
            for d in services.list_documents(s)
            if d.holder_name
        ]
    if len(named) < 2:
        return {"checked": len(named), "result": "Need at least two documents with a readable name."}
    rows = compare_names(named)
    return {"checked": len(named), "all_match": all(r["match"] for r in rows), "pairs": rows}


@tool
def get_procedure_checklist(task: str) -> dict:
    """Checklist for a paperwork task (e.g. 'renew passport', 'link PAN with Aadhaar',
    'renew driving licence'). Says which needed documents the user already has,
    which are missing and which are expired."""
    match = find_procedure(task)
    if match is None:
        return {
            "error": "No checklist for that task yet.",
            "available_tasks": {k: p["title"] for k, p in PROCEDURES.items()},
        }
    key, proc = match
    with SessionLocal() as s:
        have = {}
        for d in services.list_documents(s):
            have.setdefault(d.doc_type, d)
    needs = []
    for doc_type in proc["needs"]:
        doc = have.get(doc_type)
        needs.append({
            "document": DOC_TYPES[doc_type],
            "have": doc is not None,
            "status": services.expiry_status(doc.expiry_date) if doc else "missing",
        })
    return {
        "task": proc["title"],
        "official_portal": proc["portal"],
        "steps": proc["steps"],
        "documents": needs,
    }


@tool
def add_reminder(title: str, due_date: str) -> dict:
    """Create a reminder. `due_date` is YYYY-MM-DD."""
    try:
        due = date.fromisoformat(due_date)
    except ValueError:
        return {"error": "due_date must be YYYY-MM-DD"}
    with SessionLocal() as s:
        reminder = Reminder(title=title, due_date=due)
        s.add(reminder)
        s.commit()
        return {"id": reminder.id, "title": title, "due_date": due.isoformat()}


@tool
def list_reminders() -> list[dict]:
    """Open reminders, soonest first."""
    with SessionLocal() as s:
        rows = s.scalars(
            select(Reminder).where(Reminder.done.is_(False)).order_by(Reminder.due_date)
        )
        return [{"id": r.id, "title": r.title, "due_date": r.due_date.isoformat()} for r in rows]


ALL_TOOLS = [
    list_my_documents,
    get_document_details,
    find_expiring_documents,
    check_name_consistency,
    get_procedure_checklist,
    add_reminder,
    list_reminders,
]
