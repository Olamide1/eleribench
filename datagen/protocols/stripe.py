"""Stripe-style charge objects (PRD §3.5)."""

from __future__ import annotations

import random

PROTOCOL = "stripe"


def make_reference(rng: random.Random) -> str:
    return f"ch_{rng.getrandbits(64):016x}"


def default_extras(rng: random.Random, counterparty_address: str | None = None) -> dict:
    return {}
