"""Import shim, same pattern as datagen/_schemas.py — exposes the shared
pydantic models to bench/ without turning the repo root into a package."""

from __future__ import annotations

import sys
from pathlib import Path

_SCHEMAS_PY = Path(__file__).resolve().parent.parent / "schemas" / "python"
if str(_SCHEMAS_PY) not in sys.path:
    sys.path.insert(0, str(_SCHEMAS_PY))

from models import (  # noqa: E402
    BLOCKING_ANOMALIES,
    Anomaly,
    EleriVerdict,
    SpendCategory,
    TransactionRecord,
    Verdict,
)
from pydantic import BaseModel, ConfigDict, Field  # noqa: E402


class EleriVerdictLoose(BaseModel):
    """Same fields as EleriVerdict but WITHOUT the match+blocking-anomaly business
    rule. Baselines being scored (not trained) legitimately violate that rule
    sometimes — that's a real signal about the baseline's internal consistency,
    not something the eval harness should swallow into a hard parse failure."""

    model_config = ConfigDict(extra="forbid")

    verdict: Verdict
    category: SpendCategory
    anomalies: list[Anomaly] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    reason: str


def violates_verdict_anomaly_rule(v: EleriVerdictLoose) -> bool:
    return v.verdict == Verdict.match and any(a in BLOCKING_ANOMALIES for a in v.anomalies)


__all__ = [
    "Anomaly",
    "BLOCKING_ANOMALIES",
    "EleriVerdict",
    "EleriVerdictLoose",
    "SpendCategory",
    "TransactionRecord",
    "Verdict",
    "violates_verdict_anomaly_rule",
]
