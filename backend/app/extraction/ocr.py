"""Local OCR: EasyOCR first, PaddleOCR as fallback, pypdf for text PDFs.

Engines are imported lazily and guarded, so the app runs (with OCR
reported as unavailable) when neither is installed.
"""
import io
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class OCRText:
    text: str = ""
    confidence: float = 0.0
    words: list[dict] = field(default_factory=list)
    provider: str = "none"
    available: bool = False
    notes: str = ""


_easy_reader = None
_paddle_engine = None


def _easyocr_reader():
    """Singleton EasyOCR reader (model load is expensive, ~100MB)."""
    global _easy_reader
    if _easy_reader is None:
        import easyocr

        _easy_reader = easyocr.Reader(["en"], gpu=False)
    return _easy_reader


def _paddle():
    global _paddle_engine
    if _paddle_engine is None:
        from paddleocr import PaddleOCR

        _paddle_engine = PaddleOCR(use_gpu=False, lang="en", show_log=False)
    return _paddle_engine


def _decode(file_bytes: bytes):
    import cv2
    import numpy as np

    return cv2.imdecode(np.frombuffer(file_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)


def _word(text: str, conf: float, bbox) -> dict:
    xs = [p[0] for p in bbox]
    ys = [p[1] for p in bbox]
    return {
        "text": text,
        "confidence": conf,
        "bbox": {
            "x": int(min(xs)), "y": int(min(ys)),
            "width": int(max(xs) - min(xs)), "height": int(max(ys) - min(ys)),
        },
    }


def _lines(words: list[dict]) -> list[str]:
    """Group word boxes into visual lines (engines often split one line into
    several boxes), left to right within a line, top to bottom overall."""
    rows: list[list[dict]] = []
    for w in sorted(words, key=lambda w: w["bbox"]["y"] + w["bbox"]["height"] / 2):
        mid = w["bbox"]["y"] + w["bbox"]["height"] / 2
        if rows:
            last = rows[-1]
            last_mid = sum(x["bbox"]["y"] + x["bbox"]["height"] / 2 for x in last) / len(last)
            tolerance = max(x["bbox"]["height"] for x in last) / 2
            if abs(mid - last_mid) <= tolerance:
                last.append(w)
                continue
        rows.append([w])
    return [" ".join(w["text"] for w in sorted(row, key=lambda w: w["bbox"]["x"])) for row in rows]


def _summarise(words: list[dict], provider: str) -> OCRText:
    confs = [w["confidence"] for w in words]
    avg = round(sum(confs) / len(confs), 3) if confs else 0.0
    return OCRText(
        # One visual line per text line so line-anchored patterns (e.g. "Name:") work.
        text="\n".join(_lines(words)),
        confidence=avg,
        words=words,
        provider=provider,
        available=True,
        notes=f"{len(words)} lines, avg confidence {avg}",
    )


def _extract_easyocr(file_bytes: bytes) -> OCRText:
    img = _decode(file_bytes)
    if img is None:
        return OCRText(provider="easyocr", available=True, notes="Not a decodable image.")
    results = _easyocr_reader().readtext(img)
    return _summarise([_word(str(t), float(c), b) for b, t, c in results], "easyocr")


def _extract_paddle(file_bytes: bytes) -> OCRText:
    img = _decode(file_bytes)
    if img is None:
        return OCRText(provider="paddle_ocr", available=True, notes="Not a decodable image.")
    result = _paddle().ocr(img, cls=True)
    lines = result[0] if result and result[0] else []
    words = [_word(str(line[1][0]), float(line[1][1]), line[0]) for line in lines]
    return _summarise(words, "paddle_ocr")


def extract_pdf_text(file_bytes: bytes) -> OCRText:
    """Embedded text of a PDF (no OCR; scanned PDFs come back empty)."""
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        text = "\n".join((page.extract_text() or "") for page in reader.pages).strip()
    except Exception as exc:
        return OCRText(provider="pypdf", available=True, notes=f"PDF parse failed: {exc}")
    if not text:
        return OCRText(
            provider="pypdf", available=True,
            notes="PDF has no embedded text (probably scanned). Upload a photo instead.",
        )
    return OCRText(
        text=text, confidence=1.0, provider="pypdf", available=True,
        notes=f"{len(reader.pages)} page(s) of embedded text.",
    )


def extract_text(file_bytes: bytes, mime_type: str) -> OCRText:
    if mime_type == "application/pdf":
        return extract_pdf_text(file_bytes)
    if not mime_type.startswith("image/"):
        return OCRText(notes=f"Unsupported file type {mime_type}.")
    for name, fn in (("easyocr", _extract_easyocr), ("paddle_ocr", _extract_paddle)):
        try:
            return fn(file_bytes)
        except ImportError:
            continue
        except Exception as exc:
            logger.warning("%s failed: %s", name, exc)
            return OCRText(provider=name, available=True, notes=f"OCR error: {exc}")
    return OCRText(notes="No OCR engine installed (pip install easyocr).")
