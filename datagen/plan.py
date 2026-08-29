"""Label-first planner (PRD §3.5): decides verdict/category/anomalies/protocol/
hard-negative status for every example *before* any record is rendered, and
enforces the distribution + coverage quotas. render.py turns a plan into an
actual TransactionRecord + EleriVerdict; it never gets to change the label.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from _schemas import Anomaly, BLOCKING_ANOMALIES, WARNING_ANOMALIES, Verdict
from vendor_pools import CATEGORY_PROFILES

CATEGORIES: list[str] = list(CATEGORY_PROFILES.keys())
BLOCKING: list[str] = [a.value for a in BLOCKING_ANOMALIES]
WARNING: list[str] = [a.value for a in WARNING_ANOMALIES]
ALL_ANOMALIES: list[str] = BLOCKING + WARNING

CHAIN_ONLY_ANOMALIES = {"address_poisoning_lookalike", "wrong_network_or_token", "settlement_not_found"}
# currency_mismatch's mutator assumes a card-rail mandate (currency "USD"), matching
# render_plan's mandate construction; on x402 the mandate is "USDC", which the mutator
# doesn't account for. Simpler to keep this anomaly off-chain than to make the mutator
# handle every rail's "home" currency (see train/README.md postmortem).
NON_X402_ANOMALIES = {"currency_mismatch"}

PROTOCOLS = ["stripe", "x402", "ap2", "acp"]
PROTOCOL_WEIGHTS = [0.40, 0.35, 0.15, 0.10]
NON_X402_PROTOCOLS = ["stripe", "ap2", "acp"]
NON_X402_PROTOCOL_WEIGHTS = [0.60, 0.25, 0.15]

HARD_NEGATIVE_RATE = 0.15


@dataclass
class ExamplePlan:
    id: str
    split: str
    bucket: str  # "match" | "single_anomaly" | "multi_anomaly" | "unverifiable"
    category: str
    verdict: str
    anomalies: list[str]
    protocol: str
    hard_negative: bool
    unverifiable_kind: str | None = None


def _pick_protocol(rng: random.Random, category: str, force_x402: bool, exclude_x402: bool = False) -> str:
    if force_x402 or category == "network_gas_fees":
        return "x402"
    if exclude_x402:
        return rng.choices(NON_X402_PROTOCOLS, weights=NON_X402_PROTOCOL_WEIGHTS, k=1)[0]
    return rng.choices(PROTOCOLS, weights=PROTOCOL_WEIGHTS, k=1)[0]


def build_plans(split: str, n: int, seed: int = 0) -> list[ExamplePlan]:
    rng = random.Random(seed)

    n_match = round(0.55 * n)
    n_single = round(0.30 * n)
    n_multi = round(0.10 * n)
    n_unverifiable = n - n_match - n_single - n_multi

    plans: list[ExamplePlan] = []
    counter = 0

    def next_id() -> str:
        nonlocal counter
        counter += 1
        return f"{split}_{counter:06d}"

    # --- clean matches: round-robin category for per-category coverage ---
    for i in range(n_match):
        category = CATEGORIES[i % len(CATEGORIES)]
        protocol = _pick_protocol(rng, category, force_x402=False)
        hard_negative = rng.random() < HARD_NEGATIVE_RATE
        plans.append(
            ExamplePlan(
                id=next_id(),
                split=split,
                bucket="match",
                category=category,
                verdict=Verdict.match.value,
                anomalies=[],
                protocol=protocol,
                hard_negative=hard_negative,
            )
        )

    # --- single anomaly: round-robin anomaly for per-anomaly coverage ---
    for i in range(n_single):
        anomaly = ALL_ANOMALIES[i % len(ALL_ANOMALIES)]
        force_x402 = anomaly in CHAIN_ONLY_ANOMALIES
        exclude_x402 = anomaly in NON_X402_ANOMALIES
        category = "network_gas_fees" if force_x402 else rng.choice(CATEGORIES)
        protocol = _pick_protocol(rng, category, force_x402=force_x402, exclude_x402=exclude_x402)
        verdict = Verdict.mismatch.value if anomaly in BLOCKING else Verdict.match.value
        hard_negative = rng.random() < HARD_NEGATIVE_RATE
        plans.append(
            ExamplePlan(
                id=next_id(),
                split=split,
                bucket="single_anomaly",
                category=category,
                verdict=verdict,
                anomalies=[anomaly],
                protocol=protocol,
                hard_negative=hard_negative,
            )
        )

    # --- multi anomaly: 2-3 distinct anomalies ---
    for i in range(n_multi):
        k = rng.choices([2, 3], weights=[0.8, 0.2], k=1)[0]
        anomalies = rng.sample(ALL_ANOMALIES, k)
        force_x402 = any(a in CHAIN_ONLY_ANOMALIES for a in anomalies)
        exclude_x402 = any(a in NON_X402_ANOMALIES for a in anomalies)
        category = "network_gas_fees" if force_x402 else rng.choice(CATEGORIES)
        protocol = _pick_protocol(rng, category, force_x402=force_x402, exclude_x402=exclude_x402)
        verdict = Verdict.mismatch.value if any(a in BLOCKING for a in anomalies) else Verdict.match.value
        hard_negative = rng.random() < HARD_NEGATIVE_RATE
        plans.append(
            ExamplePlan(
                id=next_id(),
                split=split,
                bucket="multi_anomaly",
                category=category,
                verdict=verdict,
                anomalies=anomalies,
                protocol=protocol,
                hard_negative=hard_negative,
            )
        )

    # --- unverifiable ---
    for i in range(n_unverifiable):
        kind = "missing_payment" if i % 2 == 0 else "missing_mandate_garbled_payment"
        protocol = "other" if kind == "missing_mandate_garbled_payment" else _pick_protocol(rng, "other_unclassified", False)
        plans.append(
            ExamplePlan(
                id=next_id(),
                split=split,
                bucket="unverifiable",
                category="other_unclassified",
                verdict=Verdict.unverifiable.value,
                anomalies=[],
                protocol=protocol,
                hard_negative=False,
                unverifiable_kind=kind,
            )
        )

    rng.shuffle(plans)
    return plans


def distribution_report(plans: list[ExamplePlan]) -> dict:
    n = len(plans)
    by_category: dict[str, int] = {}
    by_anomaly: dict[str, int] = {}
    by_verdict: dict[str, int] = {}
    by_bucket: dict[str, int] = {}
    hard_negatives = 0

    for p in plans:
        by_category[p.category] = by_category.get(p.category, 0) + 1
        by_verdict[p.verdict] = by_verdict.get(p.verdict, 0) + 1
        by_bucket[p.bucket] = by_bucket.get(p.bucket, 0) + 1
        if p.hard_negative:
            hard_negatives += 1
        for a in p.anomalies:
            by_anomaly[a] = by_anomaly.get(a, 0) + 1

    return {
        "n": n,
        "by_bucket": by_bucket,
        "by_verdict": by_verdict,
        "by_category": by_category,
        "by_anomaly": by_anomaly,
        "hard_negative_count": hard_negatives,
        "hard_negative_pct": round(100 * hard_negatives / n, 2) if n else 0.0,
        "min_category_count": min(by_category.values()) if by_category else 0,
        "min_anomaly_count": min(by_anomaly.values()) if by_anomaly else 0,
    }
