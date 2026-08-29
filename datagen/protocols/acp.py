"""ACP — Agentic Commerce Protocol checkout/receipt shapes (PRD §3.5)."""

from __future__ import annotations

import random

PROTOCOL = "acp"


def make_reference(rng: random.Random) -> str:
    return f"acp_ord_{rng.getrandbits(40):010x}"


def default_extras(rng: random.Random, counterparty_address: str | None = None) -> dict:
    return {}
