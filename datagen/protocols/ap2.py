"""AP2 — agentic mandate/intent-attestation shaped payments (PRD §3.5)."""

from __future__ import annotations

import random

PROTOCOL = "ap2"


def make_reference(rng: random.Random) -> str:
    return f"ap2_intent_{rng.getrandbits(40):010x}"


def default_extras(rng: random.Random, counterparty_address: str | None = None) -> dict:
    return {}
