"""Per-model $/1M-token pricing for cost-per-1k-audits reporting (PRD §3.7,
§4). Verified against provider pricing pages/announcements on 2026-08-26 —
re-check before trusting this for a large run; prices change.
"""

from __future__ import annotations

PRICING_PER_MTOK: dict[str, dict] = {
    "claude-haiku-4-5": {
        "input": 1.00,
        "output": 5.00,
        "source": "Anthropic pricing table, cached 2026-06-24 via claude-api skill",
    },
    "gpt-4o-mini": {
        "input": 0.15,
        "output": 0.60,
        "source": "web search 2026-08-26 (devtk.ai, cloudzero.com) — cached input is $0.075/MTok, not modeled here",
    },
}


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    p = PRICING_PER_MTOK[model]
    return (input_tokens / 1_000_000) * p["input"] + (output_tokens / 1_000_000) * p["output"]
