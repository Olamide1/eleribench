"""Prompt construction shared by every baseline runner — identical system
prompt, identical few-shot set, identical output schema, per PRD §3.7."""

from __future__ import annotations

import json

from _schemas import Anomaly, SpendCategory, Verdict
from few_shot import load_few_shot
from output_schema import ELERI_VERDICT_JSON_SCHEMA  # noqa: F401  (re-exported below as OPENAI_VERDICT_SCHEMA)
from prompt import SYSTEM_PROMPT  # noqa: F401  (re-exported: this module's public API includes SYSTEM_PROMPT)


def _record_to_user_content(record: dict) -> str:
    return json.dumps(record, indent=2)


def build_few_shot_messages() -> list[dict]:
    """Returns alternating user/assistant turns for the fixed 10-example few-shot set."""
    messages: list[dict] = []
    for ex in load_few_shot():
        messages.append({"role": "user", "content": _record_to_user_content(ex["input"])})
        messages.append({"role": "assistant", "content": json.dumps(ex["output"])})
    return messages


def build_messages(record: dict) -> list[dict]:
    """Full message list for one eval call: few-shot history + the record to classify."""
    return build_few_shot_messages() + [{"role": "user", "content": _record_to_user_content(record)}]


# OpenAI's structured-outputs schema is the same shape every strict-JSON consumer
# needs (Anthropic, vLLM) — defined once in ../schemas/python/output_schema.py.
OPENAI_VERDICT_SCHEMA: dict = ELERI_VERDICT_JSON_SCHEMA
