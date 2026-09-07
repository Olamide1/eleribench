#!/usr/bin/env python3
"""Builds bench/results/leaderboard.md from every bench/results/*_summary.json —
the "results table" PRD §4 requires: accuracy, per-anomaly F1, ECE, cost/1k audits.

Usage: python bench/leaderboard.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from runners import RUNNERS  # noqa: E402

RESULTS_DIR = Path(__file__).parent / "results"


def main() -> int:
    summaries = sorted(RESULTS_DIR.glob("*_summary.json"))
    if not summaries:
        print("No summary files found in bench/results/. Run run_eval.py first.")
        return 1

    rows = [json.loads(p.read_text()) for p in summaries]
    rows.sort(key=lambda r: -r["anomaly"]["macro_f1"])

    lines = [
        "# EleriBench leaderboard",
        "",
        f"Test set: `{rows[0]['test_file']}`, n={rows[0]['n']} (see `../datagen/MANIFEST.json` for the sha256 hash and generation seed).",
        "",
        "| model | verdict acc | verdict macro-F1 | category acc | anomaly macro-F1 | anomaly micro-F1 | ECE (10-bin) | parse failures | cost / 1k audits |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['model']} "
            f"| {r['verdict']['accuracy']:.3f} "
            f"| {r['verdict']['macro_f1']:.3f} "
            f"| {r['category']['accuracy']:.3f} "
            f"| {r['anomaly']['macro_f1']:.3f} "
            f"| {r['anomaly']['micro_f1']:.3f} "
            f"| {r['ece_10bin']:.3f} "
            f"| {r['parse_failures']}/{r['n']} "
            f"| ${r['cost_usd_per_1k_audits']:.4f} |"
        )

    lines += ["", "## Per-anomaly F1 (hardest anomalies called out per PRD §3.7)", ""]
    anomaly_names = sorted(rows[0]["anomaly"]["per_anomaly"].keys())
    header = "| anomaly | " + " | ".join(r["model"] for r in rows) + " |"
    sep = "|---" * (len(rows) + 1) + "|"
    lines += [header, sep]
    for a in anomaly_names:
        vals = [f"{r['anomaly']['per_anomaly'][a]['f1']:.3f}" for r in rows]
        lines.append(f"| {a} | " + " | ".join(vals) + " |")

    lines += ["", "## Decision gate (PRD §7 Phase 2 acceptance)", ""]
    # This gate only ever governed whether frontier baselines alone were good enough
    # to skip fine-tuning — restrict it to RUNNERS-registered baselines so a
    # fine-tuned model's own summary sitting in this same results/ dir (e.g.
    # eleri-1.5b) doesn't get evaluated against a gate that isn't about it.
    baseline_rows = [r for r in rows if r["model"] in RUNNERS]
    gate_hit = [r for r in baseline_rows if r["anomaly"]["macro_f1"] >= 0.98]
    if gate_hit:
        lines.append(
            f"**Gate triggered:** {', '.join(r['model'] for r in gate_hit)} already hit ≥ 98% anomaly macro-F1 "
            "at this cost — revisit the fine-tune rationale before Phase 3 per PRD §7."
        )
    elif baseline_rows:
        best = baseline_rows[0]
        lines.append(
            f"No baseline hit the 98% anomaly-F1 gate (best: {best['model']} at {best['anomaly']['macro_f1']:.3f}). "
            "Proceed to Phase 3 (fine-tune) as planned."
        )
    else:
        lines.append("No baseline results found in `results/` — gate not evaluated.")

    out_path = RESULTS_DIR / "leaderboard.md"
    out_path.write_text("\n".join(lines) + "\n")
    print(f"Wrote {out_path}")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
