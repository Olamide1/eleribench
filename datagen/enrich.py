#!/usr/bin/env python3
"""Optional Claude enrichment pass (PRD §3.5's "Claude produces parameterized
variations... purposes, agent names, log noise"). Paraphrases only the two
free-text fields (activity.intent, output.reason) of already-rendered,
already-labelled examples from render.py/generate.py — it can add lexical
diversity but it structurally CANNOT change verdict/category/anomalies/
amounts/vendors/timestamps, because those aren't in its output schema at all.

Safety net on top of that structural guarantee: every number that appears in
the original text must still appear in Claude's rewrite, or that item falls
back to the original deterministic text untouched. Never trust-and-write.

Usage (cost-controlled test run):
  python datagen/enrich.py --in datagen/output/test_sample.jsonl \
      --out datagen/output/test_sample.enriched.jsonl --limit 20

Needs ANTHROPIC_API_KEY (loaded from ../.env if present).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _schemas import LabelledExample  # noqa: E402

import anthropic
from pydantic import BaseModel

# Sonnet 5 intro pricing runs through 2026-08-31; standard rate resumes after.
# https://www.anthropic.com/pricing — verify before relying on this for a large run.
PRICING_PER_MTOK = {
    "claude-sonnet-5": {"input": 2.00, "output": 10.00, "note": "intro pricing through 2026-08-31, then $3/$15"},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00, "note": "standard pricing"},
}

NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


class EnrichedItem(BaseModel):
    id: str
    intent: str
    reason: str


class EnrichmentBatch(BaseModel):
    items: list[EnrichedItem]


SYSTEM_PROMPT = """You rewrite two free-text fields of synthetic agent-payment audit records for lexical diversity: `intent` (what the agent said it was doing) and `reason` (why the auditor reached its verdict).

Hard rules:
- Preserve every number, amount, currency code, vendor name, date, and percentage EXACTLY as given (same digits, same string) — only change surrounding prose, sentence structure, and word choice.
- Preserve every fact: do not add, remove, or contradict any claim in the original text.
- `reason` must stay one sentence, under 30 tokens, and must still clearly state the decisive fact(s).
- `intent` should read like a short agent-log line, not a formal report.
- Return exactly one item per input id, in the same order.
"""


def build_user_message(items: list[dict]) -> str:
    payload = [
        {
            "id": it["id"],
            "category": it["category"],
            "verdict": it["verdict"],
            "anomalies": it["anomalies"],
            "current_intent": it["intent"],
            "current_reason": it["reason"],
        }
        for it in items
    ]
    return "Rewrite intent and reason for each record:\n\n" + json.dumps(payload, indent=2)


def numbers_preserved(original: str, rewritten: str) -> bool:
    orig_nums = set(NUMBER_RE.findall(original))
    new_nums = set(NUMBER_RE.findall(rewritten))
    return orig_nums.issubset(new_nums)


def enrich_batch(
    client: "anthropic.Anthropic",
    examples: list[dict],
    model: str,
) -> tuple[list[dict], dict]:
    """Returns (enriched examples, usage dict). Falls back per-item on any failure."""
    items = [
        {
            "id": ex["id"],
            "category": ex["output"]["category"],
            "verdict": ex["output"]["verdict"],
            "anomalies": ex["output"]["anomalies"],
            "intent": (ex["input"].get("activity") or {}).get("intent", ""),
            "reason": ex["output"]["reason"],
        }
        for ex in examples
        if (ex["input"].get("activity") or {}).get("intent")
    ]
    if not items:
        return examples, {"input_tokens": 0, "output_tokens": 0, "fallback_count": 0}

    response = client.messages.parse(
        model=model,
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_message(items)}],
        output_format=EnrichmentBatch,
    )
    by_id = {ex["id"]: ex for ex in examples}
    fallback_count = 0

    parsed_by_id = {it.id: it for it in response.parsed_output.items}

    for orig_id, orig_ex in by_id.items():
        item = parsed_by_id.get(orig_id)
        if item is None:
            fallback_count += 1
            continue

        orig_intent = (orig_ex["input"].get("activity") or {}).get("intent", "")
        orig_reason = orig_ex["output"]["reason"]

        intent_ok = numbers_preserved(orig_intent, item.intent) if orig_intent else True
        reason_ok = numbers_preserved(orig_reason, item.reason)

        candidate = json.loads(json.dumps(orig_ex))  # deep copy
        if intent_ok and orig_ex["input"].get("activity"):
            candidate["input"]["activity"]["intent"] = item.intent
        elif orig_intent:
            fallback_count += 1
        if reason_ok:
            candidate["output"]["reason"] = item.reason
        else:
            fallback_count += 1

        try:
            LabelledExample.model_validate(candidate)
        except Exception:
            fallback_count += 1
            continue

        by_id[orig_id] = candidate

    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "fallback_count": fallback_count,
    }
    return list(by_id.values()), usage


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="claude-sonnet-5", choices=list(PRICING_PER_MTOK.keys()))
    ap.add_argument("--batch-size", type=int, default=20)
    ap.add_argument("--limit", type=int, default=None, help="only enrich the first N examples (cost control)")
    args = ap.parse_args()

    examples = [json.loads(line) for line in Path(args.inp).open()]
    if args.limit:
        examples = examples[: args.limit]

    client = anthropic.Anthropic()

    total_in = total_out = total_fallback = 0
    enriched_all: list[dict] = []

    for i in range(0, len(examples), args.batch_size):
        batch = examples[i : i + args.batch_size]
        enriched, usage = enrich_batch(client, batch, args.model)
        enriched_all.extend(enriched)
        total_in += usage["input_tokens"]
        total_out += usage["output_tokens"]
        total_fallback += usage["fallback_count"]
        print(f"batch {i // args.batch_size + 1}: {len(batch)} examples, "
              f"{usage['input_tokens']}in/{usage['output_tokens']}out tokens, "
              f"{usage['fallback_count']} fell back to deterministic text")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.out).open("w") as f:
        for ex in enriched_all:
            f.write(json.dumps(ex) + "\n")

    price = PRICING_PER_MTOK[args.model]
    cost = (total_in / 1_000_000) * price["input"] + (total_out / 1_000_000) * price["output"]
    per_example_cost = cost / len(examples) if examples else 0

    print(f"\nWrote {len(enriched_all)} examples to {args.out}")
    print(f"Total tokens: {total_in} in / {total_out} out")
    print(f"Fallbacks (kept deterministic text): {total_fallback}/{len(examples)}")
    print(f"Measured cost for this run ({args.model}, {price['note']}): ${cost:.4f}")
    print(f"  => ${per_example_cost * 1000:.4f} per 1,000 examples")
    print(f"  => extrapolated to full 33,000-example dataset: ${per_example_cost * 33000:.2f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
