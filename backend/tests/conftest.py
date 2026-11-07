import os
import tempfile

# Must run before any `app` import: point storage + DB at a throwaway dir and
# make sure no real LLM key is picked up from the machine.
_tmp = tempfile.mkdtemp(prefix="docmitra-test-")
os.environ["STORAGE_DIR"] = _tmp
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db".replace("\\", "/")
os.environ["GOOGLE_API_KEY"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["LLM_MODEL"] = "google_genai:gemini-2.5-flash"

import pytest  # noqa: E402

from app.db import Base, engine, init_db  # noqa: E402
from app.extraction import ocr  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    init_db()
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def fake_ocr(monkeypatch):
    """Make OCR return the given text instead of running EasyOCR."""

    def set_text(text: str):
        monkeypatch.setattr(
            ocr, "extract_text",
            lambda _b, _m: ocr.OCRText(text=text, confidence=0.9, provider="fake", available=True),
        )

    return set_text


def png_bytes(width=800, height=600, value=200) -> bytes:
    import cv2
    import numpy as np

    img = np.full((height, width, 3), value, dtype=np.uint8)
    # Some edges so the sharpness check passes.
    for x in range(0, width, 20):
        img[:, x:x + 2] = 0
    return cv2.imencode(".png", img)[1].tobytes()
