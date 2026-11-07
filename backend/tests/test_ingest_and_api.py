from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.agents.ingest import run_ingest
from app.main import app
from tests import samples
from tests.conftest import png_bytes


def test_ingest_classifies_and_extracts(fake_ocr):
    fake_ocr(samples.PASSPORT)
    result = run_ingest(png_bytes(), "image/png")
    assert result["doc_type"] == "PASSPORT"
    assert result["holder_name"] == "RAHUL KUMAR SHARMA"
    assert result["expiry_date"] == "2028-01-09"
    assert result["quality"]["decodable"] is True


def test_ingest_respects_type_hint(fake_ocr):
    fake_ocr(samples.PUC)
    assert run_ingest(png_bytes(), "image/png", "PUC")["doc_type"] == "PUC"


def test_ingest_stops_on_undecodable_image(fake_ocr):
    fake_ocr(samples.PAN)
    result = run_ingest(b"not an image", "image/png")
    assert result["doc_type"] == "UNKNOWN"
    assert "ocr_text" not in result  # OCR never ran
    assert any("not a readable image" in n for n in result["notes"])


def test_ingest_flags_blurry_photo(fake_ocr):
    fake_ocr(samples.PAN)
    flat = png_bytes(value=128)
    import cv2
    import numpy as np

    blurry = cv2.imencode(".png", np.full((800, 800, 3), 128, dtype=np.uint8))[1].tobytes()
    assert not any("blurry" in n for n in run_ingest(flat, "image/png")["notes"])
    assert any("blurry" in n for n in run_ingest(blurry, "image/png")["notes"])


def _upload(client, fake_ocr, text, name="doc.png"):
    fake_ocr(text)
    resp = client.post("/api/documents", files={"file": (name, png_bytes(), "image/png")})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_upload_masks_ids_and_creates_reminder(fake_ocr):
    with TestClient(app) as client:
        doc = _upload(client, fake_ocr, samples.DRIVING_LICENCE)
        assert doc["doc_type"] == "DRIVING_LICENCE"
        assert doc["expiry_date"] == "2030-08-13"
        dl = next(f for f in doc["fields"] if f["key"] == "dl_number")
        assert dl["value"] == "XXXX XXXXXXX2345"
        assert "ocr_text" not in doc

        reminders = client.get("/api/reminders").json()
        assert len(reminders) == 1
        assert reminders[0]["due_date"] == (date(2030, 8, 13) - timedelta(days=30)).isoformat()

        r = client.patch(f"/api/reminders/{reminders[0]['id']}", json={"done": True})
        assert r.json()["done"] is True


def test_list_get_delete(fake_ocr):
    with TestClient(app) as client:
        doc = _upload(client, fake_ocr, samples.PAN)
        assert [d["id"] for d in client.get("/api/documents").json()] == [doc["id"]]
        assert client.get(f"/api/documents/{doc['id']}").json()["holder_name"] == "RAHUL KUMAR SHARMA"
        assert client.get(f"/api/documents/{doc['id']}/file").status_code == 200
        assert client.delete(f"/api/documents/{doc['id']}").status_code == 204
        assert client.get(f"/api/documents/{doc['id']}").status_code == 404


def test_rejects_bad_uploads():
    with TestClient(app) as client:
        r = client.post("/api/documents", files={"file": ("a.txt", b"hi", "text/plain")})
        assert r.status_code == 415
        r = client.post("/api/documents", files={"file": ("a.png", png_bytes(), "image/png")},
                        data={"doc_type": "NOPE"})
        assert r.status_code == 422


def test_name_check(fake_ocr):
    with TestClient(app) as client:
        _upload(client, fake_ocr, samples.PAN)
        _upload(client, fake_ocr, samples.AADHAAR)
        body = client.get("/api/checks/names").json()
        assert body["documents"] == 2
        assert body["pairs"][0]["match"] is True


def test_chat_without_key_returns_503():
    with TestClient(app) as client:
        r = client.post("/api/chat", json={"message": "hi"})
        assert r.status_code == 503
        assert "API key" in r.json()["detail"]
