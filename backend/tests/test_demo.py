"""Public demo mode: synthetic documents are seeded and writes are blocked."""
from fastapi.testclient import TestClient

from app import demo
from app.config import settings
from app.db import SessionLocal
from app.main import app


def test_seed_creates_varied_documents():
    with SessionLocal() as s:
        assert demo.seed_demo(s) == 7
        assert demo.seed_demo(s) == 0  # idempotent
    client = TestClient(app)
    docs = client.get("/api/documents").json()
    types = {d["doc_type"] for d in docs}
    assert {"AADHAAR", "PAN", "DRIVING_LICENCE", "PASSPORT", "RC", "VEHICLE_INSURANCE", "PUC"} <= types
    statuses = {d["doc_type"]: d["status"] for d in docs}
    assert statuses["VEHICLE_INSURANCE"] == "expired"
    assert statuses["PASSPORT"] == "expiring"
    assert statuses["RC"] == "valid"
    pairs = client.get("/api/checks/names").json()["pairs"]
    assert any(not p["match"] for p in pairs), "demo should show a name mismatch"
    for d in docs:
        for f in d["fields"]:
            if f["sensitive"]:
                assert "X" in f["value"], f"{f['key']} should be masked"


def test_demo_blocks_uploads_and_deletes(monkeypatch):
    monkeypatch.setattr(settings, "demo_mode", True)
    client = TestClient(app)
    r = client.post("/api/documents", files={"file": ("a.png", b"x", "image/png")})
    assert r.status_code == 403
    with SessionLocal() as s:
        demo.seed_demo(s)
    doc_id = client.get("/api/documents").json()[0]["id"]
    assert client.delete(f"/api/documents/{doc_id}").status_code == 403
    assert client.get(f"/api/documents/{doc_id}/file").status_code == 404
    assert client.get("/api/health").json()["demo_mode"] is True
