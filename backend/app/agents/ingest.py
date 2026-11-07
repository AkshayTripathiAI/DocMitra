"""Document intake pipeline as a LangGraph StateGraph.

quality -> ocr -> classify -> extract -> summarise

Fully deterministic: no LLM call, so uploads work offline and the
assistant only ever sees what this pipeline extracted.
"""
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from ..extraction import classify as classifier
from ..extraction import fields as fx
from ..extraction import ocr, quality


class IngestState(TypedDict, total=False):
    file_bytes: bytes
    mime_type: str
    doc_type_hint: str | None  # user-chosen type; skips classification
    quality: dict | None
    ocr_text: str
    ocr_words: list[dict]
    ocr_provider: str
    doc_type: str
    fields: list[dict]
    holder_name: str | None
    expiry_date: str | None  # ISO date
    notes: list[str]


def check_quality(state: IngestState) -> IngestState:
    metrics = quality.analyze_image(state["file_bytes"], state["mime_type"])
    if metrics is None:
        return {"quality": None, "notes": []}
    return {"quality": metrics.to_dict(), "notes": list(metrics.issues)}


def after_quality(state: IngestState) -> str:
    q = state.get("quality")
    return "summarise" if q is not None and not q["decodable"] else "run_ocr"


def run_ocr(state: IngestState) -> IngestState:
    result = ocr.extract_text(state["file_bytes"], state["mime_type"])
    notes = list(state.get("notes", []))
    if not result.text:
        notes.append(result.notes or "No text found.")
    return {
        "ocr_text": result.text,
        "ocr_words": result.words,
        "ocr_provider": result.provider,
        "notes": notes,
    }


def classify(state: IngestState) -> IngestState:
    hint = state.get("doc_type_hint")
    if hint and hint in classifier.DOC_TYPES:
        return {"doc_type": hint}
    doc_type, _score = classifier.classify(state.get("ocr_text", ""))
    return {"doc_type": doc_type}


def extract(state: IngestState) -> IngestState:
    return {
        "fields": fx.extract_fields(
            state["doc_type"], state.get("ocr_text", ""), state.get("ocr_words")
        )
    }


def summarise(state: IngestState) -> IngestState:
    doc_type = state.get("doc_type", "UNKNOWN")
    found = state.get("fields", [])
    notes = list(state.get("notes", []))
    holder = fx.field_value(found, fx.HOLDER_FIELD.get(doc_type, "")) or None
    expiry = fx.parse_date(fx.field_value(found, fx.EXPIRY_FIELD.get(doc_type, "")))
    if doc_type in fx.EXPIRY_FIELD and expiry is None and state.get("ocr_text"):
        notes.append("Could not read an expiry date. You can add a reminder by hand.")
    if doc_type == "UNKNOWN" and state.get("ocr_text"):
        notes.append("Document type not recognised. Pick the type and re-scan.")
    return {
        "doc_type": doc_type,
        "fields": found,
        "holder_name": holder,
        "expiry_date": expiry.isoformat() if expiry else None,
        "notes": notes,
    }


def build_ingest_graph():
    graph = StateGraph(IngestState)
    graph.add_node("check_quality", check_quality)
    graph.add_node("run_ocr", run_ocr)
    graph.add_node("classify", classify)
    graph.add_node("extract", extract)
    graph.add_node("summarise", summarise)
    graph.add_edge(START, "check_quality")
    graph.add_conditional_edges("check_quality", after_quality, ["run_ocr", "summarise"])
    graph.add_edge("run_ocr", "classify")
    graph.add_edge("classify", "extract")
    graph.add_edge("extract", "summarise")
    graph.add_edge("summarise", END)
    return graph.compile()


ingest_graph = build_ingest_graph()


def run_ingest(file_bytes: bytes, mime_type: str, doc_type_hint: str | None = None) -> IngestState:
    return ingest_graph.invoke(
        {"file_bytes": file_bytes, "mime_type": mime_type, "doc_type_hint": doc_type_hint}
    )


def ingest_text(text: str, doc_type_hint: str | None = None) -> IngestState:
    """Run classify -> extract -> summarise on text that is already OCR'd (demo seeding, tests)."""
    state: IngestState = {"ocr_text": text, "ocr_words": [], "ocr_provider": "sample",
                          "doc_type_hint": doc_type_hint, "notes": []}
    state.update(classify(state))
    state.update(extract(state))
    state.update(summarise(state))
    return state
