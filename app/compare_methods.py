"""Compare Method 1 (structured prompt) against Method 1 + 2 (plus pseudocode step).

    python -m app.compare_methods cases.json --runs 3 --out compare_results.json

cases.json: [{"name": "...", "text": "...", "input_type": "real_code",
              "expected_algorithm": "dijkstra"}, ...]
`input_type` and `expected_algorithm` are optional.

A generation that raises an error counts as validity 0.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections import defaultdict

from app.agents.graph_planner import run_graph_planner
from app.agents.pseudocode_planner import run_pseudocode_graph_planner
from app.validity import check_validity, validity_rate

MODES = {"method1": run_graph_planner, "method1+2": run_pseudocode_graph_planner}


async def generate(planner, case: dict) -> dict:
    """Run one generation and return one result row (never raises)."""
    row = {"case": case["name"], "input_type": case.get("input_type", "unlabelled"),
           "error": None, "algorithm": None, "algorithm_correct": None, "validity": 0.0,
           "violated": [], "tokens": 0, "pseudocode_status": None}
    start = time.perf_counter()
    try:
        spec, tokens = await planner(case["text"])
    except Exception as exc:
        row["error"] = str(exc)
    else:
        result = check_validity(spec)
        expected = case.get("expected_algorithm")
        row.update(algorithm=spec["algorithm"], validity=result.score, violated=list(result.violated),
                   tokens=tokens, pseudocode_status=spec.get("pseudocode_status"),
                   algorithm_correct=None if expected is None else spec["algorithm"] == expected)
    row["seconds"] = round(time.perf_counter() - start, 2)
    return row


def _stats(rows: list[dict]) -> dict:
    graded = [r["algorithm_correct"] for r in rows if r["algorithm_correct"] is not None]
    return {
        "generations": len(rows),
        "errors": sum(r["error"] is not None for r in rows),
        "validity_rate_pct": round(validity_rate([r["validity"] for r in rows]), 2),
        "algorithm_accuracy_pct": round(100 * sum(graded) / len(graded), 2) if graded else None,
        "avg_tokens": round(sum(r["tokens"] for r in rows) / len(rows)) if rows else 0,
        "avg_seconds": round(sum(r["seconds"] for r in rows) / len(rows), 2) if rows else 0,
        "pseudocode_fallbacks": sum(r["pseudocode_status"] not in (None, "ok") for r in rows),
    }


def summarize(rows: list[dict]) -> dict:
    """Overall and per-input-type statistics for each mode."""
    summary: dict = {}
    for mode in MODES:
        mode_rows = [r for r in rows if r["mode"] == mode]
        by_type = defaultdict(list)
        for r in mode_rows:
            by_type[r["input_type"]].append(r)
        summary[mode] = {"overall": _stats(mode_rows), "by_input_type": {t: _stats(v) for t, v in by_type.items()}}
    return summary


async def compare(cases: list[dict], runs: int, delay: float) -> list[dict]:
    rows = []
    for case in cases:
        for run in range(runs):
            for mode, planner in MODES.items():  # alternate modes so both see similar load
                row = await generate(planner, case)
                rows.append({**row, "mode": mode, "run": run})
                await asyncio.sleep(delay)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("cases_file")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--delay", type=float, default=0.0, help="seconds to wait between calls (rate limits)")
    parser.add_argument("--out", default="compare_results.json")
    args = parser.parse_args()
    with open(args.cases_file, encoding="utf-8") as f:
        cases = json.load(f)
    rows = asyncio.run(compare(cases, args.runs, args.delay))
    summary = summarize(rows)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "rows": rows}, f, indent=2, ensure_ascii=False)
    print(json.dumps(summary, indent=2))
    print(f"\nPer-generation rows saved to {args.out}")


if __name__ == "__main__":
    main()
