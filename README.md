# EleriBench

A benchmark for agent-spend verification: given a payment an AI agent made and
what it was actually authorized to spend, does a model correctly say whether
the payment matches the authorization — and, if not, why?

Every AI agent that can pay for things eventually needs something checking
its payments against its mandate. EleriBench measures how well a model does
that job: not "is this a reasonable purchase" in the abstract, but "does
this specific payment match this specific authorization" — vendor, amount,
purpose, expiry, and a handful of failure modes (overspend, wrong vendor,
duplicate charges, lookalike wallet addresses, and more) that are easy for a
human to miss skimming a statement and easy for a naive LLM prompt to get
wrong.

**[Eleri](https://huggingface.co/theakomolafe/eleri-1.5b)**, a 1.5B
fine-tune, is the reference model this benchmark was built to develop and
evaluate. It's also used in production by Sawa, a consumer product for
auditing AI agent spend — but the benchmark, test set, and evaluation
harness here are independent of both.

## Leaderboard

Locked test set, n=1,500. Full methodology below; see
[`bench/results/leaderboard.md`](bench/results/leaderboard.md) for the raw
generated table and per-anomaly breakdown.

| model | verdict acc | anomaly macro-F1 | ECE (10-bin) | cost / 1k audits |
|---|---|---|---|---|
| **eleri-1.5b** | **0.972** | **0.989** | **0.050** | $0.62 |
| claude-haiku-4-5 (few-shot) | 0.808 | 0.684 | 0.128 | $5.26 |
| gpt-4o-mini (few-shot) | 0.682 | 0.392 | 0.240 | $0.60 |

Eleri-1.5b's cost figure is from the training-time evaluation harness in
this repo (a naive per-call GPU-time estimate, not a production serving
benchmark). A separate, unpublished project (Sawa) reports ~$0.04–0.08/1k
audits with batched, constrained decoding — that number isn't verifiable
from this repo, so treat it as a pointer, not a claim this benchmark backs.
GPT-4o-mini is nominally cheaper per audit than Eleri here, but at roughly a
third the accuracy on the metric that matters most (anomaly detection) —
cost alone isn't the useful comparison.

Both baselines get the identical prompt: one system prompt, a fixed 10-example
few-shot set (drawn only from hand-written examples, never generated data, so
it can't leak a test example), and the same constrained-JSON output schema.
Nothing about the prompt was tuned per-model.

Want to add a baseline? Open a PR — `bench/runners/` is a small provider
registry (`AnthropicRunner`, `OpenAIRunner` today); adding one is additive.

## Running it

```bash
# tested on Python 3.12.1
python3 -m venv .venv
.venv/bin/pip install -r bench/runners/requirements.txt

export ANTHROPIC_API_KEY=...
export OPENAI_API_KEY=...

.venv/bin/python bench/run_eval.py --model claude-haiku-4-5
.venv/bin/python bench/run_eval.py --model gpt-4o-mini
.venv/bin/python bench/leaderboard.py
```

`run_eval.py --limit N` runs a quick partial pass. Full details, including
what's tracked vs. gitignored in `bench/results/`, in
[`bench/README.md`](bench/README.md).

## Limitations

- **Fully synthetic.** Every example — train, val, test — comes from
  `datagen/`'s label-first templates, not from real agent transaction logs.
  A planned realism check against ~100 real x402 settlements was never done
  (see the acceptance checklist in [`datagen/README.md`](datagen/README.md)).
- **No independent review of the generated labels.** A 300-example
  human-review sample and log template exist (`datagen/qa_sample.py`,
  `datagen/qa_review_log.md`), but the review itself was never carried out.
- **The held-out test set is not a distribution-shift test.** `test.jsonl`
  uses vendors and agent IDs disjoint from training, but the same generator
  and the same protocol templates. A genuinely out-of-distribution slice
  (`test_ood.jsonl`, a receipt format that appears nowhere in training) is
  specified in [`bench/README.md`](bench/README.md) but not built. Nothing
  here measures how any of these models handle a record shaped differently
  from what they've seen.
- **eleri-1.5b's headline numbers include a real parse-failure rate.** 42 of
  1,500 test outputs (2.8%) failed to parse as valid JSON under plain greedy
  decoding and count as misses in the accuracy figures above — they are not
  excluded from the denominator (see `bench/metrics.py`). Constrained
  decoding closes this structurally in Eleri's serving setup; the number
  above is from this harness as it actually ran, without that.
- **Self-reported.** All three leaderboard rows were run and reported by the
  person who built eleri-1.5b, using the harness in this repo. None of it
  has been independently reproduced. `run_eval.py` is a public, one-command
  harness specifically so that can change.

## The task

Given a `TransactionRecord` — a `mandate` (budget, allowed vendors, allowed
purposes, expiry), an `activity` (what the agent says it was doing), and a
`payment` (what actually got charged) — output a verdict:

- **`match`** — the payment is authorized.
- **`mismatch`** — it isn't, with one or more specific anomalies.
- **`unverifiable`** — there isn't enough information to say either way.

Plus a spend `category` (16-way classification), a `confidence` score, and a
one-line `reason`. Full schema:
[`schemas/json/transaction_record.schema.json`](schemas/json/transaction_record.schema.json)
(input) and
[`schemas/json/verdict.schema.json`](schemas/json/verdict.schema.json)
(output) — also available as TypeScript types and Python (pydantic) models
in [`schemas/`](schemas/), kept in sync by hand across all three.

**Taxonomy:**

- **16 spend categories** — compute_inference, data_api, storage_bandwidth,
  saas_subscription, software_tools, content_media, communications,
  advertising_promotion, commerce_goods, commerce_services,
  travel_logistics, financial_fees, network_gas_fees, human_services,
  deposits_transfers, other_unclassified.
- **15 anomalies** (9 blocking a `match` verdict, 6 warning-only) —
  blocking: amount_exceeds_mandate, vendor_not_allowed, mandate_expired,
  no_matching_mandate, purpose_mismatch, duplicate_charge,
  address_poisoning_lookalike, wrong_network_or_token, settlement_not_found.
  Warning: budget_period_at_risk, velocity_anomaly, amount_discrepancy,
  currency_mismatch, split_transaction_pattern, stale_settlement.

`address_poisoning_lookalike` deserves a callout: an on-chain payment to a
wallet address that matches the authorized one at the prefix and suffix but
differs in the middle — the kind of substitution a human visually skimming
an address would very plausibly miss, and a real attack pattern against
agents making on-chain payments (see `schemas/examples/eleri_examples.json`'s
`anom_address_poisoning_lookalike` for a worked example).

## Metrics

- **Verdict accuracy / macro-F1** — 3-way (match/mismatch/unverifiable).
- **Category accuracy / macro-F1** — 16-way.
- **Anomaly F1** — multi-label (a payment can trigger more than one
  anomaly), both micro and macro, plus a full per-anomaly breakdown so a
  model that's strong on average but blind to one specific attack pattern
  doesn't hide behind the aggregate.
- **ECE (10-bin)** — expected calibration error on the model's own
  confidence score. A model that's right 90% of the time when it says
  "90% confident" is more useful in production than one that's equally
  accurate on average but overconfident on its mistakes.
- **Cost per 1,000 audits** — $/1M-token pricing × actual token usage per
  call (see [`bench/pricing.py`](bench/pricing.py)), or GPU-time cost for a
  self-hosted model.

## The test set

1,500 examples, generation seed 999, sha256
`ae5a1cdaffd60a6edfef4d495a7ea3780429e4d5c4baf4997a6bf8e42b01a5bd` (see
[`datagen/MANIFEST.json`](datagen/MANIFEST.json) for the full generation
report — distribution by category/anomaly/verdict, and the same for the
30,000-example train split). Vendor pools and agent IDs are disjoint from
train, so a model can't have memorized the specific vendors or agents in the
test set during fine-tuning.

Synthetic, not scraped — generated **label-first**: the ground-truth verdict
and anomaly are decided before the record is rendered, not inferred after
the fact, so every label is exact by construction rather than approximate.
See [`datagen/README.md`](datagen/README.md) for the generation pipeline.

`datagen/MANIFEST.json`'s `notes` field documents three label-quality bugs
found and fixed during Eleri's own development: currency leaking into
unrelated examples, purpose/intent sampled independently causing false
mismatches, and one anomaly type that was genuinely unlearnable from the
input fields as originally rendered. Train/val/test were regenerated after
the fixes, and both baselines in the leaderboard above were rerun on the
regenerated test set — this README only reports post-fix numbers. The
pre-fix numbers aren't reproduced here because the artifacts that produced
them weren't kept, and a number this repo can't point to isn't one we'll
state as fact.

10 hand-written, human-verified examples (one per spend category isn't
included in every split, but the full 33-example set covering every
category/anomaly/verdict combination is in
[`schemas/examples/eleri_examples.json`](schemas/examples/eleri_examples.json))
back the fixed few-shot set every baseline sees — never generated data, so
the few-shot set can't leak a test example.

## Repo layout

| Dir | Contents |
|---|---|
| `schemas/` | JSON Schema + TypeScript + Python (pydantic) definitions for the transaction record and verdict, plus the 33 hand-verified examples. |
| `datagen/` | The synthetic generator — label-first planner, protocol-specific renderers (x402/AP2/ACP/Stripe-shaped records), vendor pools, QA sampler. |
| `bench/` | The benchmark itself: locked test set, prompting/few-shot setup, baseline runners, metrics, leaderboard generator, results. |

## License

Apache 2.0 — see [`LICENSE`](LICENSE). Eleri itself is a fine-tune of
[Qwen2.5-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct)
(also Apache 2.0).
