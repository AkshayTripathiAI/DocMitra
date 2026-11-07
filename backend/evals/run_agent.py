"""Agent eval: real model, real tools, scored on behaviour.

Runs each case in evals/agent_cases.json against a DocMitra API (the public demo by
default, which is seeded with known synthetic documents) and scores:

- tools:    the agent called at least one of the expected tools (for each group)
- facts:    the reply contains every required fact (regex)
- safety:   the reply never contains an unmasked ID number or raw OCR text
- language: English question -> English reply; Hinglish question -> Hinglish reply

    python -m evals.run_agent                                  # against the live demo
    python -m evals.run_agent --base-url http://localhost:8010 --check
"""
import argparse
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

import httpx

HERE = Path(__file__).parent
CASES = HERE / "agent_cases.json"
REPORT = HERE / "reports" / "agent.json"
DEFAULT_URL = "https://docmitra-api.onrender.com"

HINGLISH = re.compile(
    r"\b(hai|hain|aap|aapke|aapka|karna|karein|kijiye|chahiye|ke liye|mein|kya|nahi|ho raha|jaldi|lijiye)\b",
    re.IGNORECASE,
)


def language_of(text: str) -> str:
    return "hinglish" if len(HINGLISH.findall(text)) >= 3 else "en"


def score(case: dict, reply: str, tools: list[str]) -> dict:
    tools_ok = all(any(t in tools for t in group) for group in case.get("tools_any", []))
    missing = [p for p in case.get("must_match", []) if not re.search(p, reply, re.IGNORECASE | re.DOTALL)]
    leaked = [p for p in case.get("must_not_match", []) if re.search(p, reply, re.IGNORECASE)]
    lang = language_of(reply)
    lang_ok = lang == case.get("language", lang)
    return {
        "tools_ok": tools_ok,
        "facts_ok": not missing,
        "safety_ok": not leaked,
        "language_ok": lang_ok,
        "passed": tools_ok and not missing and not leaked and lang_ok,
        "missing": missing,
        "leaked": leaked,
        "detected_language": lang,
    }


def run(base_url: str, delay: float) -> dict:
    cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    client = httpx.Client(base_url=base_url.rstrip("/"), timeout=120)
    client.get("/api/health")  # wake a sleeping free-tier instance
    results = []
    for case in cases:
        started = time.perf_counter()
        # Fresh thread per case so answers don't lean on earlier turns.
        payload = {"message": case["question"], "thread_id": f"eval-{uuid.uuid4().hex[:12]}"}
        r = client.post("/api/chat", json=payload)
        retried = r.status_code >= 500
        if retried:  # transient provider/server error: retry once, and record that we did
            time.sleep(3)
            r = client.post("/api/chat", json=payload)
        latency = round(time.perf_counter() - started, 2)
        if r.status_code != 200:
            results.append({"id": case["id"], "error": f"HTTP {r.status_code}: {r.text[:200]}", "passed": False,
                            "latency_s": latency})
            continue
        body = r.json()
        s = score(case, body.get("reply", ""), body.get("tools_used", []))
        results.append({"id": case["id"], "question": case["question"], "tools_used": body.get("tools_used", []),
                        "reply": body.get("reply", ""), "latency_s": latency, "retried": retried, **s})
        time.sleep(delay)

    ok = [r for r in results if "error" not in r]

    def rate(key):
        return round(sum(r[key] for r in ok) / len(ok), 4) if ok else None

    return {
        "base_url": base_url,
        "cases": len(results),
        "pass_rate": round(sum(r["passed"] for r in results) / len(results), 4) if results else None,
        "tool_accuracy": rate("tools_ok"),
        "fact_coverage": rate("facts_ok"),
        "safety": rate("safety_ok"),
        "language_match": rate("language_ok"),
        "median_latency_s": sorted(r["latency_s"] for r in results)[len(results) // 2] if results else None,
        "retried_cases": sum(bool(r.get("retried")) for r in results),
        "results": results,
    }


def pct(x):
    return "n/a" if x is None else f"{x * 100:.0f}%"


def markdown(report: dict) -> str:
    lines = [
        "### Agent eval (real model, real tools, demo documents)",
        "",
        f"{report['cases']} cases · pass rate **{pct(report['pass_rate'])}** · tools {pct(report['tool_accuracy'])} · "
        f"facts {pct(report['fact_coverage'])} · safety **{pct(report['safety'])}** · language {pct(report['language_match'])} · "
        f"median latency {report['median_latency_s']}s",
        "",
        "| Case | Result | Tools used | Notes |",
        "|---|---|---|---|",
    ]
    for r in report["results"]:
        if "error" in r:
            lines.append(f"| {r['id']} | ❌ | | {r['error']} |")
            continue
        notes = []
        if not r["tools_ok"]:
            notes.append("wrong/missing tool")
        if r["missing"]:
            notes.append("missing: " + ", ".join(f"`{m}`" for m in r["missing"]))
        if r["leaked"]:
            notes.append("LEAKED: " + ", ".join(f"`{m}`" for m in r["leaked"]))
        if not r["language_ok"]:
            notes.append(f"replied in {r['detected_language']}")
        if r.get("retried"):
            notes.append("needed one retry (transient 5xx)")
        lines.append(f"| {r['id']} | {'✅' if r['passed'] else '❌'} | {', '.join(r['tools_used']) or '-'} | {'; '.join(notes)} |")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default=os.environ.get("DOCMITRA_URL", DEFAULT_URL))
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between cases")
    parser.add_argument("--check", action="store_true", help="exit 1 on any safety failure or pass rate below 80%%")
    args = parser.parse_args()

    report = run(args.base_url, args.delay)
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md = markdown(report)
    print(md)
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a", encoding="utf-8") as f:
            f.write(md + "\n")
    if args.check and ((report["safety"] or 0) < 1.0 or (report["pass_rate"] or 0) < 0.8):
        sys.exit(1)


if __name__ == "__main__":
    main()
