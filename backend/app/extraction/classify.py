"""Guess the document type from OCR text with keyword + pattern scoring."""
import re

DOC_TYPES = {
    "AADHAAR": "Aadhaar card",
    "PAN": "PAN card",
    "DRIVING_LICENCE": "Driving licence",
    "PASSPORT": "Passport",
    "RC": "Vehicle registration (RC)",
    "VEHICLE_INSURANCE": "Vehicle insurance",
    "PUC": "Pollution certificate (PUC)",
    "UNKNOWN": "Other document",
}

# (pattern, weight). Patterns are case-insensitive unless they need case.
_SIGNALS: dict[str, list[tuple[str, int]]] = {
    "AADHAAR": [
        (r"aadhaar|aadhar|आधार", 3),
        (r"unique identification authority|uidai", 3),
        (r"\b\d{4}\s\d{4}\s\d{4}\b", 2),
        (r"vid\s*:?\s*\d{4}\s?\d{4}\s?\d{4}\s?\d{4}", 1),
    ],
    "PAN": [
        (r"income\s*tax\s*department", 3),
        (r"permanent\s*account\s*number", 3),
        (r"(?-i:\b[A-Z]{5}\d{4}[A-Z]\b)", 2),
    ],
    "DRIVING_LICENCE": [
        (r"driving\s*licen[cs]e", 3),
        (r"\bDL\s*No\b", 2),
        (r"(?-i:\b[A-Z]{2}[-\s]?\d{2}[-\s]?\d{4}\d{7}\b)", 2),
        (r"\bCOV\b|class\s*of\s*vehicle", 1),
    ],
    "PASSPORT": [
        (r"\bpassport\b", 3),
        (r"republic\s*of\s*india", 1),
        (r"P<IND", 3),
        (r"(?-i:\b[A-Z]\d{7}\b)", 1),
    ],
    "RC": [
        (r"certificate\s*of\s*registration|registration\s*certificate", 3),
        (r"chassis", 2),
        (r"engine\s*(?:no|number)", 1),
        (r"registered\s*owner|owner'?s?\s*name", 1),
    ],
    "VEHICLE_INSURANCE": [
        (r"\bpolicy\s*(?:no|number)\b", 2),
        (r"insurance", 2),
        (r"\bIDV\b|insured\s*declared\s*value", 2),
        (r"premium", 1),
    ],
    "PUC": [
        (r"pollution\s*under\s*control|\bPUCC?\b", 3),
        (r"emission", 1),
        (r"\bCO\s*%|\bHC\s*\(?ppm", 1),
    ],
}

MIN_SCORE = 3


def classify(text: str) -> tuple[str, int]:
    """Return (doc_type, score). UNKNOWN when nothing scores MIN_SCORE."""
    if not text.strip():
        return "UNKNOWN", 0
    scores = {
        doc_type: sum(w for pat, w in signals if re.search(pat, text, re.IGNORECASE))
        for doc_type, signals in _SIGNALS.items()
    }
    best = max(scores, key=scores.get)
    if scores[best] < MIN_SCORE:
        return "UNKNOWN", scores[best]
    return best, scores[best]
