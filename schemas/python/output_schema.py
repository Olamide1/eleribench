"""Clean, strict-mode-compatible JSON Schema for EleriVerdict — shared by
../../bench (OpenAI structured outputs) and ../../serve (vLLM structured
outputs). Built from the taxonomy enums rather than loading
../json/verdict.schema.json directly, since that file carries $schema/$id/
$comment keys that strict-mode consumers don't want and don't need.
"""

from __future__ import annotations

from models import Anomaly, SpendCategory, Verdict

ELERI_VERDICT_JSON_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["verdict", "category", "anomalies", "confidence", "reason"],
    "properties": {
        "verdict": {"type": "string", "enum": [v.value for v in Verdict]},
        "category": {"type": "string", "enum": [c.value for c in SpendCategory]},
        "anomalies": {
            "type": "array",
            "items": {"type": "string", "enum": [a.value for a in Anomaly]},
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reason": {"type": "string"},
    },
}
