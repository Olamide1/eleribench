"""Deterministic renderer: ExamplePlan -> validated LabelledExample. Pure
Python, zero API calls, zero cost — this is what guarantees "labels are exact,
never inferred afterwards" (PRD §3.5). enrich.py (optional, costs API credit)
only ever touches free-text fields on top of this output, never the label-
bearing structure.
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone

from _schemas import LabelledExample
from plan import ExamplePlan
from protocols import REGISTRY as PROTOCOL_REGISTRY
from vendor_pools import (
    CATEGORY_PROFILES,
    SAMPLE_WALLET_ADDRESSES,
    lookalike_domain,
    poisoned_address,
    vendor_pool_for_split,
)

EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)
HORIZON_DAYS = 236  # 2026-01-01 .. 2026-08-25ish, matches "today" in this project


def _log_uniform(rng: random.Random, lo: float, hi: float) -> float:
    return math.exp(rng.uniform(math.log(lo), math.log(hi)))


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _random_window_start(rng: random.Random) -> datetime:
    return EPOCH + timedelta(days=rng.uniform(0, HORIZON_DAYS), seconds=rng.uniform(0, 86400))


class Ctx:
    """Mutable render context threaded through anomaly mutators."""

    def __init__(self, plan: ExamplePlan, rng: random.Random):
        self.plan = plan
        self.rng = rng
        profile = CATEGORY_PROFILES[plan.category]
        self.vendor_pool = vendor_pool_for_split(plan.category, plan.split)

        self.vendor = rng.choice(self.vendor_pool)
        # purpose/intent are sampled as an aligned pair (see vendor_pools.CategoryProfile
        # docstring) — independent sampling was a confirmed bug that muddied the
        # purpose_mismatch training signal.
        purpose_idx = rng.randrange(len(profile.purposes))
        self.purpose = profile.purposes[purpose_idx]
        self.intent = profile.intents[purpose_idx]
        # Default currency always matches what the mandate will use (set below in
        # render_plan) — only m_currency_mismatch should ever introduce a deviation.
        # A prior version randomized this unconditionally (20% EUR) regardless of
        # anomaly, which leaked unlabeled currency mismatches into ~10% of ALL
        # examples and corrupted the currency_mismatch training signal.
        self.currency = "USDC" if plan.protocol == "x402" else "USD"
        self.period = rng.choices(["monthly", "weekly", "one_time"], weights=[0.5, 0.3, 0.2])[0]

        self.payment_amount = round(_log_uniform(rng, 0.05, 500), 4 if plan.protocol == "x402" else 2)
        self.budget_amount = round(self.payment_amount * rng.uniform(3, 50), 2)

        self.window_start = _random_window_start(rng)
        self.window_end = self.window_start + timedelta(minutes=rng.uniform(0.5, 8))
        self.payment_timestamp = self.window_end + timedelta(seconds=rng.uniform(2, 90))
        self.mandate_expiry = self.window_start + timedelta(days=rng.uniform(30, 300))
        self.mandate_created = self.window_start - timedelta(days=rng.uniform(1, 60))

        self.allowed_vendors = [self.vendor]
        self.denied_vendors: list[str] = []
        self.allowed_purposes = [self.purpose]
        self.payment_vendor = self.vendor

        heldout_wallets = SAMPLE_WALLET_ADDRESSES[-1:]
        train_wallets = SAMPLE_WALLET_ADDRESSES[:-1]
        wallet_pool = heldout_wallets if plan.split in ("val", "test") else train_wallets
        self.wallet_address = rng.choice(wallet_pool)
        self.counterparty_address = self.wallet_address
        if plan.protocol == "x402" and plan.category == "network_gas_fees":
            self.allowed_vendors = ["base_network"]
            self.payment_vendor = "base_network"

        self.meta: dict = {"bucket": plan.bucket, "hard_negative": plan.hard_negative}
        self.reason_parts: list[str] = []
        self.omit_mandate = False
        self.omit_activity = False
        self.omit_payment = False
        self.payment_amount_present = True
        self.settlement_status: str | None = "settled" if plan.protocol == "x402" else None
        self.tx_hash_override: str | None = None
        self.token_contract_override: str | None = None
        self.chain_override: str | None = None


# ---------- anomaly mutators (each edits ctx in place, appends a reason clause) ----------


def m_amount_exceeds_mandate(ctx: Ctx) -> None:
    ratio = 1.005 if ctx.plan.hard_negative else ctx.rng.uniform(1.2, 3.0)
    ctx.budget_amount = round(ctx.payment_amount / ratio, 2)
    ctx.reason_parts.append(
        f"charge of {ctx.payment_amount} exceeds the {ctx.budget_amount} {ctx.period} mandate cap"
    )


def m_vendor_not_allowed(ctx: Ctx) -> None:
    if ctx.plan.hard_negative:
        ctx.payment_vendor = lookalike_domain(ctx.vendor)
    else:
        other_categories = [c for c in CATEGORY_PROFILES if c != ctx.plan.category]
        other = ctx.rng.choice(other_categories)
        ctx.payment_vendor = ctx.rng.choice(vendor_pool_for_split(other, ctx.plan.split))
    ctx.reason_parts.append(f"vendor {ctx.payment_vendor} is not on the mandate's allowed-vendor list")


def m_mandate_expired(ctx: Ctx) -> None:
    delta = timedelta(minutes=ctx.rng.uniform(5, 90)) if ctx.plan.hard_negative else timedelta(days=ctx.rng.uniform(5, 120))
    ctx.mandate_expiry = ctx.payment_timestamp - delta
    ctx.mandate_created = ctx.mandate_expiry - timedelta(days=ctx.rng.uniform(30, 90))
    ctx.reason_parts.append(f"payment occurred after the mandate's expiry of {_iso(ctx.mandate_expiry)}")


def m_no_matching_mandate(ctx: Ctx) -> None:
    ctx.omit_mandate = True
    ctx.reason_parts.append("payment settled with no mandate on file authorizing this agent's spend")


def m_purpose_mismatch(ctx: Ctx) -> None:
    if ctx.plan.hard_negative:
        others = [p for p in CATEGORY_PROFILES[ctx.plan.category].purposes if p != ctx.purpose]
        chosen = ctx.rng.choice(others) if others else ctx.purpose + " (different scope)"
    else:
        other_categories = [c for c in CATEGORY_PROFILES if c != ctx.plan.category]
        other = ctx.rng.choice(other_categories)
        chosen = ctx.rng.choice(CATEGORY_PROFILES[other].purposes)
    ctx.allowed_purposes = [chosen]
    ctx.reason_parts.append(f"activity intent does not match the mandate's allowed purpose ('{chosen}')")


def m_duplicate_charge(ctx: Ctx) -> None:
    # A prior version only recorded the "original" timestamp in ctx.meta, which
    # isn't part of the model's input at all — nothing in mandate/activity/payment
    # actually indicated duplication, making this label unlearnable from a single
    # record (confirmed near-zero F1). Real exact-duplicate detection belongs to
    # Sawa's deterministic pre-check layer (hash matching against history, PRD
    # §5.4); for Eleri's single-record task, the signal has to live in the text —
    # here, the agent's own log flagging uncertainty about a prior attempt.
    original_ts = ctx.payment_timestamp - timedelta(minutes=ctx.rng.uniform(1, 20))
    ctx.meta["duplicate_of_timestamp"] = _iso(original_ts)
    ctx.intent = ctx.intent + "; retrying this payment in case the earlier attempt for the same reference didn't go through"
    ctx.reason_parts.append("activity log shows this is a retry of a payment already settled minutes earlier for the same reference")


def m_address_poisoning_lookalike(ctx: Ctx) -> None:
    ctx.allowed_vendors = [ctx.wallet_address]
    ctx.counterparty_address = poisoned_address(ctx.wallet_address)
    ctx.payment_vendor = "counterparty_wallet"
    ctx.reason_parts.append("counterparty address matches the allowlist only at prefix/suffix; the middle differs")


def m_wrong_network_or_token(ctx: Ctx) -> None:
    if ctx.rng.random() < 0.5:
        ctx.chain_override = ctx.rng.choice(["ethereum", "arbitrum", "polygon"])
        ctx.reason_parts.append(f"mandate authorizes Base settlement but payment settled on {ctx.chain_override}")
    else:
        ctx.token_contract_override = "0x000000000000000000000000000000d34dc0de"
        ctx.reason_parts.append("payment settled using an unrecognized token contract, not the expected USDC")


def m_settlement_not_found(ctx: Ctx) -> None:
    ctx.settlement_status = "not_found"
    ctx.reason_parts.append("receipt claims settlement but no matching transaction exists on-chain for this hash")


def m_budget_period_at_risk(ctx: Ctx) -> None:
    pct = ctx.rng.uniform(80, 99)
    ctx.meta["cumulative_spend_pct_of_budget"] = round(pct, 1)
    ctx.intent = ctx.intent + f"; cumulative spend this period is {pct:.0f}% of the mandate budget"
    ctx.reason_parts.append(f"cumulative period spend is now {pct:.0f}% of the mandate budget")


def m_velocity_anomaly(ctx: Ctx) -> None:
    calls = ctx.rng.randint(20, 60)
    typical = ctx.rng.randint(1, 4)
    ctx.meta["calls_last_hour"] = calls
    ctx.meta["typical_calls_per_hour"] = typical
    ctx.intent = ctx.intent + f"; this is call {calls} in the last hour vs a typical {typical}"
    ctx.reason_parts.append("call frequency is far above the agent's typical pattern for this vendor")


def m_amount_discrepancy(ctx: Ctx) -> None:
    diff_pct = ctx.rng.uniform(3, 8) if ctx.plan.hard_negative else ctx.rng.uniform(8, 15)
    quoted = round(ctx.payment_amount / (1 + diff_pct / 100), 2)
    ctx.meta["quoted_amount"] = quoted
    ctx.intent = ctx.intent + f"; quoted price was {quoted} {ctx.currency}"
    ctx.reason_parts.append(f"settled amount differs from the {quoted} {ctx.currency} quoted in the activity log")


def m_currency_mismatch(ctx: Ctx) -> None:
    mandate_currency = "USD"
    payment_currency = "EUR" if mandate_currency == "USD" else "USD"
    ctx.currency = payment_currency
    ctx.meta["mandate_currency"] = mandate_currency
    ctx.reason_parts.append(f"mandate budget is denominated in {mandate_currency} but payment settled in {payment_currency}")


def m_split_transaction_pattern(ctx: Ctx) -> None:
    cap = round(ctx.payment_amount * ctx.rng.uniform(1.02, 1.15), 2)
    ctx.budget_amount = cap
    ctx.payment_amount = round(cap * ctx.rng.uniform(0.9, 0.99), 2)
    n_charges = ctx.rng.randint(3, 6)
    ctx.meta["same_day_same_vendor_charge_count"] = n_charges
    ctx.intent = ctx.intent + f"; this is charge {n_charges} to the same vendor today, each just under the cap"
    ctx.reason_parts.append(f"{n_charges} same-day charges to the same vendor each stay just under the per-transaction cap")


def m_stale_settlement(ctx: Ctx) -> None:
    delay_days = ctx.rng.uniform(6, 10) if ctx.plan.hard_negative else ctx.rng.uniform(14, 45)
    ctx.payment_timestamp = ctx.window_end + timedelta(days=delay_days)
    ctx.reason_parts.append(f"payment settled {delay_days:.0f} days after the activity window closed")


MUTATORS = {
    "amount_exceeds_mandate": m_amount_exceeds_mandate,
    "vendor_not_allowed": m_vendor_not_allowed,
    "mandate_expired": m_mandate_expired,
    "no_matching_mandate": m_no_matching_mandate,
    "purpose_mismatch": m_purpose_mismatch,
    "duplicate_charge": m_duplicate_charge,
    "address_poisoning_lookalike": m_address_poisoning_lookalike,
    "wrong_network_or_token": m_wrong_network_or_token,
    "settlement_not_found": m_settlement_not_found,
    "budget_period_at_risk": m_budget_period_at_risk,
    "velocity_anomaly": m_velocity_anomaly,
    "amount_discrepancy": m_amount_discrepancy,
    "currency_mismatch": m_currency_mismatch,
    "split_transaction_pattern": m_split_transaction_pattern,
    "stale_settlement": m_stale_settlement,
}


def _confidence_for(plan: ExamplePlan, rng: random.Random) -> float:
    base = 0.72 if plan.hard_negative else 0.93
    if plan.bucket == "match" and not plan.anomalies:
        base = 0.7 if plan.hard_negative else 0.97
    if plan.bucket == "unverifiable":
        base = 0.55
    return round(min(0.99, max(0.5, base + rng.uniform(-0.04, 0.04))), 2)


def render_plan(plan: ExamplePlan, seed: int = 0) -> LabelledExample:
    rng = random.Random(f"{seed}:{plan.id}")
    ctx = Ctx(plan, rng)

    if plan.bucket == "unverifiable":
        return _render_unverifiable(ctx)

    for anomaly in plan.anomalies:
        MUTATORS[anomaly](ctx)

    mandate = None
    if not ctx.omit_mandate:
        mandate = {
            "mandate_id": f"m_{plan.id}",
            "budget": {"amount": ctx.budget_amount, "currency": "USDC" if plan.protocol == "x402" else "USD", "period": ctx.period},
            "allowed_vendors": ctx.allowed_vendors,
            "allowed_purposes": ctx.allowed_purposes,
            "expiry": _iso(ctx.mandate_expiry),
            "created_at": _iso(ctx.mandate_created),
        }

    activity = {
        "agent_id": f"agt_{plan.category}_{plan.split}",
        "intent": ctx.intent,
        "window_start": _iso(ctx.window_start),
        "window_end": _iso(ctx.window_end),
    }

    proto_module = PROTOCOL_REGISTRY[plan.protocol]
    payment = {
        "protocol": plan.protocol,
        "amount": ctx.payment_amount,
        "currency": ctx.currency,
        "vendor": ctx.payment_vendor,
        "timestamp": _iso(ctx.payment_timestamp),
        "reference": proto_module.make_reference(rng),
    }

    if plan.protocol == "x402":
        extras = proto_module.default_extras(rng, ctx.counterparty_address)
        if ctx.chain_override:
            extras["chain"] = ctx.chain_override
        if ctx.token_contract_override:
            extras["token_contract"] = ctx.token_contract_override
        if ctx.settlement_status:
            extras["settlement_status"] = ctx.settlement_status
        payment.update(extras)

    reason = "; ".join(ctx.reason_parts) if ctx.reason_parts else f"{ctx.purpose} charge matches allowed vendor and purpose"
    reason = reason[0].upper() + reason[1:] + "."

    output = {
        "verdict": plan.verdict,
        "category": plan.category,
        "anomalies": plan.anomalies,
        "confidence": _confidence_for(plan, rng),
        "reason": reason,
    }

    example = {
        "id": plan.id,
        "input": {"mandate": mandate, "activity": activity, "payment": payment},
        "output": output,
        "meta": ctx.meta,
    }
    return LabelledExample.model_validate(example)


def _render_unverifiable(ctx: Ctx) -> LabelledExample:
    plan = ctx.plan
    input_obj: dict = {}

    if plan.unverifiable_kind == "missing_payment":
        input_obj["mandate"] = {
            "mandate_id": f"m_{plan.id}",
            "budget": {"amount": ctx.budget_amount, "currency": "USD", "period": ctx.period},
            "allowed_vendors": ctx.allowed_vendors,
            "allowed_purposes": ctx.allowed_purposes,
            "expiry": _iso(ctx.mandate_expiry),
        }
        input_obj["activity"] = {
            "agent_id": f"agt_{plan.category}_{plan.split}",
            "intent": ctx.intent,
            "window_start": _iso(ctx.window_start),
            "window_end": _iso(ctx.window_end),
        }
        reason = "No payment/settlement record is present to verify against the mandate."
    else:
        input_obj["payment"] = {
            "protocol": "other",
            "vendor": "corrupt",
            "reference": f"ref_{plan.id}",
            "timestamp": _iso(ctx.payment_timestamp),
        }
        reason = "Payment record is truncated/unreadable and no mandate is present to compare against."

    output = {
        "verdict": "unverifiable",
        "category": "other_unclassified",
        "anomalies": [],
        "confidence": _confidence_for(plan, ctx.rng),
        "reason": reason,
    }
    example = {"id": plan.id, "input": input_obj, "output": output, "meta": ctx.meta}
    return LabelledExample.model_validate(example)
