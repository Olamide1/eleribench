#!/usr/bin/env python3
"""
Phase 0 acceptance check (PRD §7):
  "schema validates hand-written examples of every category, anomaly, and
   verdict, including unverifiable."

Validates schemas/examples/eleri_examples.json against:
  1. the JSON Schemas (schemas/json/*.schema.json)
  2. the pydantic models (schemas/python/models.py)
and checks that every SpendCategory, every Anomaly, and every Verdict
(including "unverifiable") appears at least once across the example set.

Usage: python schemas/validate.py
Exit code 0 = pass, 1 = fail.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).parent / "python"))
from models import Anomaly, EleriVerdict, LabelledExample, SpendCategory, Verdict  # noqa: E402

ROOT = Path(__file__).parent
EXAMPLES_PATH = ROOT / "examples" / "eleri_examples.json"
INPUT_SCHEMA_PATH = ROOT / "json" / "transaction_record.schema.json"
OUTPUT_SCHEMA_PATH = ROOT / "json" / "verdict.schema.json"


def load_json(path: Path) -> object:
    with path.open() as f:
        return json.load(f)


def main() -> int:
    examples = load_json(EXAMPLES_PATH)
    input_validator = Draft202012Validator(load_json(INPUT_SCHEMA_PATH))
    output_validator = Draft202012Validator(load_json(OUTPUT_SCHEMA_PATH))

    errors: list[str] = []
    seen_categories: set[str] = set()
    seen_anomalies: set[str] = set()
    seen_verdicts: set[str] = set()

    for ex in examples:
        ex_id = ex.get("id", "<no id>")

        # 1. JSON Schema validation
        for err in input_validator.iter_errors(ex["input"]):
            errors.append(f"[{ex_id}] input JSON Schema: {err.message} at {list(err.absolute_path)}")
        for err in output_validator.iter_errors(ex["output"]):
            errors.append(f"[{ex_id}] output JSON Schema: {err.message} at {list(err.absolute_path)}")

        # 2. pydantic validation (also enforces business rules, e.g. match+blocking-anomaly)
        try:
            parsed = LabelledExample.model_validate(ex)
        except Exception as e:  # pydantic ValidationError
            errors.append(f"[{ex_id}] pydantic: {e}")
            continue

        seen_categories.add(parsed.output.category.value)
        seen_anomalies.update(a.value for a in parsed.output.anomalies)
        seen_verdicts.add(parsed.output.verdict.value)

    # 3. Coverage checks
    all_categories = {c.value for c in SpendCategory}
    all_anomalies = {a.value for a in Anomaly}
    all_verdicts = {v.value for v in Verdict}

    missing_categories = all_categories - seen_categories
    missing_anomalies = all_anomalies - seen_anomalies
    missing_verdicts = all_verdicts - seen_verdicts

    if missing_categories:
        errors.append(f"Missing category coverage: {sorted(missing_categories)}")
    if missing_anomalies:
        errors.append(f"Missing anomaly coverage: {sorted(missing_anomalies)}")
    if missing_verdicts:
        errors.append(f"Missing verdict coverage: {sorted(missing_verdicts)}")

    print(f"Examples checked: {len(examples)}")
    print(f"Categories covered: {len(seen_categories)}/{len(all_categories)}")
    print(f"Anomalies covered:  {len(seen_anomalies)}/{len(all_anomalies)}")
    print(f"Verdicts covered:   {sorted(seen_verdicts)}")

    if errors:
        print(f"\nFAIL — {len(errors)} problem(s):")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("\nPASS — all examples valid, full taxonomy coverage.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
