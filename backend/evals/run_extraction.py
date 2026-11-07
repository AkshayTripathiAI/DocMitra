"""Extraction eval: classify -> extract -> summarise against the labelled dataset.

Metrics
- classification accuracy (overall, per type, per noise level)
- field accuracy: extracted value equals ground truth (after normalising case/spacing)
- field recall: a value was extracted at all
- silent error rate: a value was extracted but it is WRONG (worse than missing,
  because the user sees confident wrong data)
- holder name and expiry date accuracy (they drive mismatch checks and reminders)

    python -m evals.run_extraction                 # text tier, used in CI
    python -m evals.run_extraction --images 35     # also render N samples to PNG and run real OCR
    python -m evals.run_extraction --check         # exit 1 if below evals/thresholds.json
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

from app.agents.ingest import ingest_text, run_ingest
from app.extraction import fields as fx

HERE = Path(__file__).parent
DATASET = HERE / "data" / "extraction_v1.jsonl"
THRESHOLDS = HERE / "thresholds.json"
REPORT_DIR = HERE / "reports"


def norm(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").upper()).strip(" .")


def load(path: Path = DATASET) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def score_sample(sample: dict, result: dict) -> dict:
    exp = sample["expected"]
    got = {f["key"]: f["value"] for f in result.get("fields", [])}
    per_field = {}
    for key, truth in exp["fields"].items():
        value = got.get(key)
        per_field[key] = {
            "found": value is not None,
            "correct": value is not None and norm(value) == norm(truth),
            "got": value,
            "truth": truth,
        }
    return {
        "id": sample["id"],
        "doc_type": sample["doc_type"],
        "noise": sample["noise"],
        "predicted_type": result.get("doc_type"),
        "type_correct": result.get("doc_type") == sample["doc_type"],
        "fields": per_field,
        "holder_correct": None if exp["holder_name"] is None
        else norm(result.get("holder_name")) == norm(exp["holder_name"]),
        "expiry_correct": None if exp["expiry_date"] is None
        else result.get("expiry_date") == exp["expiry_date"],
    }


def _rate(hits: int, total: int) -> float | None:
    return round(hits / total, 4) if total else None


def aggregate(rows: list[dict]) -> dict:
    def summarize(subset: list[dict]) -> dict:
        f_total = f_found = f_correct = 0
        for r in subset:
            for f in r["fields"].values():
                f_total += 1
                f_found += f["found"]
                f_correct += f["correct"]
        holder = [r["holder_correct"] for r in subset if r["holder_correct"] is not None]
        expiry = [r["expiry_correct"] for r in subset if r["expiry_correct"] is not None]
        return {
            "samples": len(subset),
            "classification_accuracy": _rate(sum(r["type_correct"] for r in subset), len(subset)),
            "field_accuracy": _rate(f_correct, f_total),
            "field_recall": _rate(f_found, f_total),
            "silent_error_rate": _rate(f_found - f_correct, f_total),
            "holder_name_accuracy": _rate(sum(holder), len(holder)),
            "expiry_accuracy": _rate(sum(expiry), len(expiry)),
        }

    by_type, by_noise, by_field = defaultdict(list), defaultdict(list), defaultdict(lambda: [0, 0, 0])
    for r in rows:
        by_type[r["doc_type"]].append(r)
        by_noise[r["noise"]].append(r)
        for key, f in r["fields"].items():
            stats = by_field[f"{r['doc_type']}.{key}"]
            stats[0] += 1
            stats[1] += f["found"]
            stats[2] += f["correct"]
    failures = [
        {"id": r["id"], "field": key, "got": f["got"], "truth": f["truth"]}
        for r in rows for key, f in r["fields"].items() if not f["correct"]
    ]
    return {
        "overall": summarize(rows),
        "by_noise": {k: summarize(v) for k, v in sorted(by_noise.items())},
        "by_type": {k: summarize(v) for k, v in sorted(by_type.items())},
        "by_field": {k: {"n": n, "recall": _rate(found, n), "accuracy": _rate(ok, n)}
                     for k, (n, found, ok) in sorted(by_field.items())},
        "failures": failures,
    }


def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.1f}%"


def markdown(report: dict, title: str) -> str:
    o = report["overall"]
    lines = [
        f"### {title}",
        "",
        f"{o['samples']} samples · classification **{pct(o['classification_accuracy'])}** · "
        f"field accuracy **{pct(o['field_accuracy'])}** · silent errors **{pct(o['silent_error_rate'])}** · "
        f"expiry **{pct(o['expiry_accuracy'])}** · holder name **{pct(o['holder_name_accuracy'])}**",
        "",
        "| Slice | Samples | Classification | Field accuracy | Field recall | Silent errors | Expiry |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for group in ("by_noise", "by_type"):
        for name, s in report[group].items():
            lines.append(
                f"| {name} | {s['samples']} | {pct(s['classification_accuracy'])} | {pct(s['field_accuracy'])} | "
                f"{pct(s['field_recall'])} | {pct(s['silent_error_rate'])} | {pct(s['expiry_accuracy'])} |"
            )
    weak = [(k, v) for k, v in report["by_field"].items() if (v["accuracy"] or 0) < 0.9]
    if weak:
        lines += ["", "Weakest fields (accuracy < 90%):", ""]
        for k, v in sorted(weak, key=lambda kv: kv[1]["accuracy"] or 0)[:10]:
            lines.append(f"- `{k}`: accuracy {pct(v['accuracy'])}, recall {pct(v['recall'])} (n={v['n']})")
    return "\n".join(lines)


def run_text(samples: list[dict]) -> list[dict]:
    return [score_sample(s, ingest_text(s["text"])) for s in samples]


def render_png(text: str) -> bytes:
    """Draw document text onto a card-like image so the real OCR path is exercised."""
    import io

    from PIL import Image, ImageDraw, ImageFont

    lines = text.split("\n")
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 30)
    except OSError:
        try:
            font = ImageFont.truetype("arial.ttf", 30)
        except OSError:
            font = ImageFont.load_default(size=30)
    width = 60 + max(int(font.getlength(line)) for line in lines)
    img = Image.new("RGB", (max(width, 900), 60 + 46 * len(lines)), (250, 248, 240))
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((30, 30 + 46 * i), line, fill=(20, 20, 30), font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def run_images(samples: list[dict]) -> list[dict]:
    rows = []
    for i, s in enumerate(samples, 1):
        result = run_ingest(render_png(s["text"]), "image/png")
        rows.append(score_sample(s, result))
        print(f"  image {i}/{len(samples)}: {s['id']} -> {result.get('doc_type')}", file=sys.stderr)
    return rows


def check(report: dict) -> list[str]:
    limits = json.loads(THRESHOLDS.read_text())
    failures = []
    for metric, bound in limits.get("min", {}).items():
        value = report["overall"][metric]
        if value is None or value < bound:
            failures.append(f"{metric} = {pct(value)} is below the minimum {pct(bound)}")
    for metric, bound in limits.get("max", {}).items():
        value = report["overall"][metric]
        if value is not None and value > bound:
            failures.append(f"{metric} = {pct(value)} is above the maximum {pct(bound)}")
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--images", type=int, default=0, help="also run real OCR on N clean+light samples")
    parser.add_argument("--check", action="store_true", help="fail if below evals/thresholds.json")
    args = parser.parse_args()

    samples = load()
    REPORT_DIR.mkdir(exist_ok=True)
    text_report = aggregate(run_text(samples))
    (REPORT_DIR / "extraction_text.json").write_text(json.dumps(text_report, indent=2))
    md = markdown(text_report, "Extraction eval (text tier: OCR text with simulated OCR noise)")

    if args.images:
        # Evenly spread across types; skip "heavy" (images add their own real OCR noise).
        pool = [s for s in samples if s["noise"] == "clean"]
        step = max(1, len(pool) // args.images)
        image_report = aggregate(run_images(pool[::step][: args.images]))
        (REPORT_DIR / "extraction_images.json").write_text(json.dumps(image_report, indent=2))
        md += "\n\n" + markdown(image_report, "Extraction eval (image tier: rendered images through EasyOCR)")

    print(md)
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a", encoding="utf-8") as f:
            f.write(md + "\n")

    if args.check:
        failures = check(text_report)
        if failures:
            print("\nEval thresholds failed:\n- " + "\n- ".join(failures), file=sys.stderr)
            sys.exit(1)
        print("\nAll eval thresholds passed.")


if __name__ == "__main__":
    main()
