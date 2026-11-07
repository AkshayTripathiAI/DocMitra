from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from app.agents import assistant, tools
from app.main import app
from tests import samples
from tests.conftest import png_bytes


class FakeToolModel(GenericFakeChatModel):
    """Replays scripted AI messages; tool binding is a no-op."""

    def bind_tools(self, _tools, **_kwargs):
        return self


def _seed(fake_ocr, *texts):
    with TestClient(app) as client:
        for text in texts:
            fake_ocr(text)
            client.post("/api/documents", files={"file": ("d.png", png_bytes(), "image/png")})


def test_agent_calls_tool_then_answers(fake_ocr):
    _seed(fake_ocr, samples.PAN)
    model = FakeToolModel(messages=iter([
        AIMessage(content="", tool_calls=[{"name": "list_my_documents", "args": {}, "id": "c1"}]),
        AIMessage(content="You have a PAN card."),
    ]))
    out = assistant.chat("what documents do I have?", "t1", model=model)
    assert out == {"reply": "You have a PAN card.", "tools_used": ["list_my_documents"]}


def test_checklist_tool_reports_missing_and_expired(fake_ocr):
    _seed(fake_ocr, samples.PAN)
    result = tools.get_procedure_checklist.invoke({"task": "link pan with aadhaar"})
    assert result["task"] == "Link PAN with Aadhaar"
    by_doc = {d["document"]: d for d in result["documents"]}
    assert by_doc["PAN card"]["have"] is True
    assert by_doc["Aadhaar card"]["status"] == "missing"


def test_checklist_tool_unknown_task():
    result = tools.get_procedure_checklist.invoke({"task": "get a fishing permit"})
    assert "available_tasks" in result


def test_tools_never_leak_full_ids(fake_ocr):
    _seed(fake_ocr, samples.AADHAAR, samples.PAN)
    dumped = str(tools.list_my_documents.invoke({}))
    for doc in tools.list_my_documents.invoke({}):
        dumped += str(tools.get_document_details.invoke({"document_id": doc["id"]}))
    assert "2345 6789 0123" not in dumped
    assert "ABCPS1234K" not in dumped


def test_name_consistency_tool(fake_ocr):
    _seed(fake_ocr, samples.PAN, samples.RC, samples.DRIVING_LICENCE)
    result = tools.check_name_consistency.invoke({})
    assert result["checked"] == 3
    assert result["all_match"] is True


def test_add_and_list_reminders():
    tools.add_reminder.invoke({"title": "Renew PUC", "due_date": "2030-01-01"})
    assert tools.add_reminder.invoke({"title": "x", "due_date": "01/01/2030"})["error"]
    assert [r["title"] for r in tools.list_reminders.invoke({})] == ["Renew PUC"]
