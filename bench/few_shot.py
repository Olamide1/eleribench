"""Fixed 10-example few-shot set used identically for every baseline (PRD
§3.7: "identical prompt + 10 few-shot examples + same constrained-JSON
schema"). Drawn from the hand-written, human-verified examples in
../schemas/examples/eleri_examples.json — never from generated train/test
data, so there's no chance a baseline's few-shot prompt leaks a test example.
"""

from __future__ import annotations

import json
from pathlib import Path

_EXAMPLES_PATH = Path(__file__).resolve().parent.parent / "schemas" / "examples" / "eleri_examples.json"

# Spans both verdicts that need blocking anomalies, both that don't, and both
# unverifiable cases — deliberately not just "one of each anomaly".
FEW_SHOT_IDS = [
    "cat_compute_inference",
    "cat_travel_logistics",
    "anom_amount_exceeds_mandate",
    "anom_vendor_not_allowed",
    "anom_no_matching_mandate",
    "anom_address_poisoning_lookalike",
    "anom_budget_period_at_risk",
    "anom_currency_mismatch",
    "unverifiable_missing_payment",
    "unverifiable_missing_mandate_and_activity_garbled_payment",
]


def load_few_shot() -> list[dict]:
    all_examples = {ex["id"]: ex for ex in json.loads(_EXAMPLES_PATH.read_text())}
    missing = [i for i in FEW_SHOT_IDS if i not in all_examples]
    if missing:
        raise KeyError(f"few-shot ids not found in {_EXAMPLES_PATH}: {missing}")
    return [all_examples[i] for i in FEW_SHOT_IDS]
