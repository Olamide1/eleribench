"""Import shim: exposes ../schemas/python/models.py as `eleri_schemas` without
turning the repo root into a package. Every datagen module imports from here.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCHEMAS_PY = Path(__file__).resolve().parent.parent / "schemas" / "python"
if str(_SCHEMAS_PY) not in sys.path:
    sys.path.insert(0, str(_SCHEMAS_PY))

from models import (  # noqa: E402  (re-exported for datagen consumers)
    Activity,
    Anomaly,
    BLOCKING_ANOMALIES,
    WARNING_ANOMALIES,
    Budget,
    EleriVerdict,
    FeeBreakdown,
    LabelledExample,
    Mandate,
    MandatePeriod,
    Payment,
    PaymentProtocol,
    SettlementStatus,
    SpendCategory,
    ToolCall,
    TransactionRecord,
    Verdict,
)

__all__ = [
    "Activity",
    "Anomaly",
    "BLOCKING_ANOMALIES",
    "WARNING_ANOMALIES",
    "Budget",
    "EleriVerdict",
    "FeeBreakdown",
    "LabelledExample",
    "Mandate",
    "MandatePeriod",
    "Payment",
    "PaymentProtocol",
    "SettlementStatus",
    "SpendCategory",
    "ToolCall",
    "TransactionRecord",
    "Verdict",
]
