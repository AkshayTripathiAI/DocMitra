"""OCR-tolerant comparison of names across documents (stdlib only)."""
import difflib
import re
from itertools import combinations

NAME_MATCH_THRESHOLD = 0.85

_TITLES = {"MR", "MRS", "MS", "MISS", "DR", "SRI", "SMT", "SHRI", "KUMARI", "KUM", "LATE"}


def normalize_name(value: str) -> str:
    """Uppercase, drop titles/punctuation, collapse spaces."""
    text = re.sub(r"[^A-Z ]", " ", (value or "").upper())
    return " ".join(t for t in text.split() if t not in _TITLES)


def name_similarity(a: str, b: str) -> float:
    """0-1. Token-sorted ratio handles reordered names; raw ratio handles OCR typos."""
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    sorted_a, sorted_b = " ".join(sorted(na.split())), " ".join(sorted(nb.split()))
    ratio = max(
        difflib.SequenceMatcher(None, sorted_a, sorted_b).ratio(),
        difflib.SequenceMatcher(None, na, nb).ratio(),
    )
    # An initial ("R KUMAR" vs "RAHUL KUMAR") is a common, legitimate variation.
    ta, tb = na.split(), nb.split()
    if len(ta) == len(tb) and ta[-1] == tb[-1] and all(
        x == y or (len(x) == 1 and y.startswith(x)) or (len(y) == 1 and x.startswith(y))
        for x, y in zip(ta, tb)
    ):
        ratio = max(ratio, 0.9)
    return round(ratio, 3)


def compare_names(names: list[tuple[str, str]]) -> list[dict]:
    """Pairwise check of (label, name) items. Returns one row per pair."""
    rows = []
    for (la, a), (lb, b) in combinations(names, 2):
        score = name_similarity(a, b)
        rows.append({
            "a": la, "b": lb, "name_a": a, "name_b": b,
            "similarity": score, "match": score >= NAME_MATCH_THRESHOLD,
        })
    return rows
