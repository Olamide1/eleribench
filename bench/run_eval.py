#!/usr/bin/env python3
"""EleriBench eval harness (PRD §4, §7 Phase 2): one command, works against
any registered baseline. `--limit N` for a cost-controlled test run before
committing to the full 1,500-example test set.

Usage:
  python bench/run_eval.py --model claude-haiku-4-5 --limit 30
  python bench/run_eval.py --model gpt-4o-mini --test bench/test.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _schemas import violates_verdict_anomaly_rule  # noqa: E402
from metrics import (  # noqa: E402
    anomaly_metrics,
    classification_metrics,
    confidence_threshold_coverage,
    expected_calibration_error,
)
from pricing import cost_usd  # noqa: E402
from prompting import build_messages  # noqa: E402
from runners import RUNNERS  # noqa: E402

ALL_ANOMALIES = [
    "amount_exceeds_mandate", "vendor_not_allowed", "mandate_expired", "no_matching_mandate",
    "purpose_mismatch", "duplicate_charge", "address_poisoning_lookalike", "wrong_network_or_token",
    "settlement_not_found", "budget_period_at_risk", "velocity_anomaly", "amount_discrepancy",
    "currency_mismatch", "split_transaction_pattern", "stale_settlement",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, choices=list(RUNNERS.keys()))
    ap.add_argument("--test", default=str(Path(__file__).parent / "test.jsonl"))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out-dir", default=str(Path(__file__).parent / "results"))
    args = ap.parse_args()

    examples = [json.loads(line) for line in Path(args.test).open()]
    if args.limit:
        examples = examples[: args.limit]

    runner = RUNNERS[args.model]()

    pred_verdicts: list[str | None] = []
    pred_categories: list[str | None] = []
    pred_anomalies: list[list[str]] = []
    pred_confidences: list[float] = []
    gold_verdicts: list[str] = []
    gold_categories: list[str] = []
    gold_anomalies: list[list[str]] = []
    business_rule_violations = 0
    errors: list[dict] = []
    total_in_tokens = total_out_tokens = 0

    predictions_path = Path(args.out_dir) / f"{args.model}_predictions.jsonl"
    predictions_path.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    with predictions_path.open("w") as pred_f:
        for i, ex in enumerate(examples):
            messages = build_messages(ex["input"])
            parsed, usage, error = runner.predict(messages)
            total_in_tokens += usage["input_tokens"]
            total_out_tokens += usage["output_tokens"]

            gold = ex["output"]
            gold_verdicts.append(gold["verdict"])
            gold_categories.append(gold["category"])
            gold_anomalies.append(gold["anomalies"])

            if parsed is None:
                pred_verdicts.append(None)
                pred_categories.append(None)
                pred_anomalies.append([])
                pred_confidences.append(0.0)
                errors.append({"id": ex.get("id", i), "error": error})
            else:
                if violates_verdict_anomaly_rule(parsed):
                    business_rule_violations += 1
                pred_verdicts.append(parsed.verdict.value)
                pred_categories.append(parsed.category.value)
                pred_anomalies.append([a.value for a in parsed.anomalies])
                pred_confidences.append(parsed.confidence)

            pred_f.write(json.dumps({
                "id": ex.get("id", i),
                "gold": gold,
                "pred": None if parsed is None else json.loads(parsed.model_dump_json()),
                "error": error,
            }) + "\n")

            if (i + 1) % 25 == 0 or (i + 1) == len(examples):
                elapsed = time.time() - t0
                print(f"  {i + 1}/{len(examples)} ({elapsed:.0f}s elapsed)", file=sys.stderr)

    verdict_correct = [p == g for p, g in zip(pred_verdicts, gold_verdicts)]

    verdict_m = classification_metrics(pred_verdicts, gold_verdicts)
    category_m = classification_metrics(pred_categories, gold_categories)
    anomaly_m = anomaly_metrics(pred_anomalies, gold_anomalies, ALL_ANOMALIES)
    ece = expected_calibration_error(pred_confidences, verdict_correct)
    tau_report = confidence_threshold_coverage(pred_confidences, verdict_correct, target_accuracy=0.99)

    cost = cost_usd(args.model, total_in_tokens, total_out_tokens)
    cost_per_1k = (cost / len(examples)) * 1000 if examples else 0.0

    try:
        test_file_recorded = str(Path(args.test).resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        test_file_recorded = args.test

    summary = {
        "model": args.model,
        "n": len(examples),
        "test_file": test_file_recorded,
        "verdict": {"accuracy": verdict_m["accuracy"], "macro_f1": verdict_m["macro_f1"], "per_class": verdict_m["per_class"]},
        "category": {"accuracy": category_m["accuracy"], "macro_f1": category_m["macro_f1"]},
        "anomaly": {
            "macro_f1": anomaly_m["macro_f1"],
            "micro_f1": anomaly_m["micro_f1"],
            "per_anomaly": anomaly_m["per_anomaly"],
        },
        "ece_10bin": ece,
        "confidence_threshold_99pct": tau_report,
        "parse_failures": verdict_m["parse_failures"],
        "business_rule_violations": business_rule_violations,
        "tokens": {"input": total_in_tokens, "output": total_out_tokens},
        "cost_usd": cost,
        "cost_usd_per_1k_audits": cost_per_1k,
        "wall_clock_seconds": time.time() - t0,
    }

    summary_path = Path(args.out_dir) / f"{args.model}_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))

    print(json.dumps(summary, indent=2))
    print(f"\nPredictions: {predictions_path}")
    print(f"Summary:     {summary_path}")
    if errors:
        print(f"\n{len(errors)} errors (first 5): {errors[:5]}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
