"""
Eleri shared pydantic models — mirrors schemas/json/*.schema.json and
schemas/typescript/types.ts. Used by /datagen (construct labelled records),
/serve (constrained decoding target), and /bench (eval parsing).

Keep the three representations (JSON Schema, TS, pydantic) in sync manually;
Phase 0 is small enough that codegen isn't worth the extra moving part yet.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ---------- Taxonomies (PRD §3.2, §3.3, Appendix C.2) ----------


class SpendCategory(str, Enum):
    compute_inference = "compute_inference"
    data_api = "data_api"
    storage_bandwidth = "storage_bandwidth"
    saas_subscription = "saas_subscription"
    software_tools = "software_tools"
    content_media = "content_media"
    communications = "communications"
    advertising_promotion = "advertising_promotion"
    commerce_goods = "commerce_goods"
    commerce_services = "commerce_services"
    travel_logistics = "travel_logistics"
    financial_fees = "financial_fees"
    network_gas_fees = "network_gas_fees"
    human_services = "human_services"
    deposits_transfers = "deposits_transfers"
    other_unclassified = "other_unclassified"


class Anomaly(str, Enum):
    # Blocking (force verdict=mismatch)
    amount_exceeds_mandate = "amount_exceeds_mandate"
    vendor_not_allowed = "vendor_not_allowed"
    mandate_expired = "mandate_expired"
    no_matching_mandate = "no_matching_mandate"
    purpose_mismatch = "purpose_mismatch"
    duplicate_charge = "duplicate_charge"
    # Appendix C — chain-specific, all blocking
    address_poisoning_lookalike = "address_poisoning_lookalike"
    wrong_network_or_token = "wrong_network_or_token"
    settlement_not_found = "settlement_not_found"
    # Warning (verdict may still be match)
    budget_period_at_risk = "budget_period_at_risk"
    velocity_anomaly = "velocity_anomaly"
    amount_discrepancy = "amount_discrepancy"
    currency_mismatch = "currency_mismatch"
    split_transaction_pattern = "split_transaction_pattern"
    stale_settlement = "stale_settlement"


BLOCKING_ANOMALIES: frozenset[Anomaly] = frozenset(
    {
        Anomaly.amount_exceeds_mandate,
        Anomaly.vendor_not_allowed,
        Anomaly.mandate_expired,
        Anomaly.no_matching_mandate,
        Anomaly.purpose_mismatch,
        Anomaly.duplicate_charge,
        Anomaly.address_poisoning_lookalike,
        Anomaly.wrong_network_or_token,
        Anomaly.settlement_not_found,
    }
)

WARNING_ANOMALIES: frozenset[Anomaly] = frozenset(set(Anomaly) - BLOCKING_ANOMALIES)


class Verdict(str, Enum):
    match = "match"
    mismatch = "mismatch"
    unverifiable = "unverifiable"


class MandatePeriod(str, Enum):
    one_time = "one_time"
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    annual = "annual"


class PaymentProtocol(str, Enum):
    x402 = "x402"
    ap2 = "ap2"
    acp = "acp"
    stripe = "stripe"
    other = "other"


class SettlementStatus(str, Enum):
    settled = "settled"
    pending = "pending"
    not_found = "not_found"


# ---------- Input: TransactionRecord ----------


class Budget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: float = Field(ge=0)
    currency: str
    period: MandatePeriod


class Mandate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mandate_id: Optional[str] = None
    budget: Optional[Budget] = None
    allowed_vendors: list[str] = Field(default_factory=list)
    denied_vendors: list[str] = Field(default_factory=list)
    allowed_purposes: list[str] = Field(default_factory=list)
    expiry: Optional[datetime] = None
    created_at: Optional[datetime] = None


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="allow")

    tool: Optional[str] = None
    args: Optional[dict[str, Any]] = None
    timestamp: Optional[datetime] = None


class Activity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    intent: Optional[str] = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None


class FeeBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gas: Optional[float] = None
    facilitator_fee: Optional[float] = None


class Payment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol: Optional[PaymentProtocol] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    vendor: Optional[str] = None
    timestamp: Optional[datetime] = None
    reference: Optional[str] = None
    # Appendix C — on-chain settlement fields
    chain: Optional[str] = None
    tx_hash: Optional[str] = None
    token_contract: Optional[str] = None
    token_decimals: Optional[int] = Field(default=None, ge=0)
    counterparty_address: Optional[str] = None
    settlement_status: Optional[SettlementStatus] = None
    fee_breakdown: Optional[FeeBreakdown] = None


class TransactionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mandate: Optional[Mandate] = None
    activity: Optional[Activity] = None
    payment: Optional[Payment] = None


# ---------- Output: EleriVerdict ----------


class EleriVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: Verdict
    category: SpendCategory
    anomalies: list[Anomaly] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    reason: str

    @model_validator(mode="after")
    def _verdict_matches_anomalies(self) -> "EleriVerdict":
        """PRD §3.1: verdict=match requires no blocking anomalies present."""
        if self.verdict == Verdict.match and any(a in BLOCKING_ANOMALIES for a in self.anomalies):
            blocking = [a.value for a in self.anomalies if a in BLOCKING_ANOMALIES]
            raise ValueError(
                f"verdict=match but blocking anomalies present: {blocking}"
            )
        if len(set(self.anomalies)) != len(self.anomalies):
            raise ValueError("anomalies must be unique")
        return self


# ---------- Labelled example (datagen construction unit) ----------


class LabelledExample(BaseModel):
    """One row of train/val/test data: input + ground-truth output.

    Datagen decides `output` first (label-first construction, PRD §3.5), then
    renders `input` to match it — this model is the seam between those steps.
    """

    model_config = ConfigDict(extra="allow")

    input: TransactionRecord
    output: EleriVerdict
    # Optional provenance, not fed to the model — useful for QA/debugging.
    meta: Optional[dict[str, Any]] = None
    # Optional human-readable id, present in hand-written fixtures (schemas/examples/).
    id: Optional[str] = None
