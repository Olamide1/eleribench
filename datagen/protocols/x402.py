"""x402 — HTTP 402 payment-required settlement, predominantly USDC on Base
(PRD §3.5, Appendix C). The only protocol with on-chain fields."""

from __future__ import annotations

import random

PROTOCOL = "x402"

BASE_USDC_CONTRACT = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
USDC_DECIMALS = 6


def make_reference(rng: random.Random) -> str:
    return f"x402_{rng.getrandbits(48):012x}"


def make_tx_hash(rng: random.Random) -> str:
    return "0x" + f"{rng.getrandbits(256):064x}"


def default_extras(rng: random.Random, counterparty_address: str) -> dict:
    """Clean-case on-chain fields: settled, correct chain/token."""
    return {
        "chain": "base",
        "tx_hash": make_tx_hash(rng),
        "token_contract": BASE_USDC_CONTRACT,
        "token_decimals": USDC_DECIMALS,
        "counterparty_address": counterparty_address,
        "settlement_status": "settled",
        "fee_breakdown": {"gas": round(rng.uniform(0.01, 0.15), 4), "facilitator_fee": 0.0},
    }
