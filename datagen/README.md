# datagen — Phase 1 (in progress)

Synthetic training-data generator for Eleri. See PRD §3.5, §7 Phase 1, and Appendix C.3.

## Design: two stages, cost isolated from correctness

**Stage A — deterministic core (zero API cost, zero network).** `plan.py` decides the label first (category/verdict/anomalies/protocol/hard-negative flag) for every example and enforces the §3.5 distribution + coverage quotas *before* anything is rendered. `render.py` then turns each plan into a full `TransactionRecord`/`EleriVerdict` pair using per-anomaly mutator functions that compute the exact numeric/structural relationship the label requires (e.g. `amount_exceeds_mandate` sets `payment.amount > mandate.budget.amount` by construction). `protocols/{x402,ap2,acp,stripe}.py` hold protocol-specific field shapes. `vendor_pools.py` holds the curated realism scaffold (vendor/purpose/intent pools per category). Every rendered example is validated against `../schemas/python/models.py` before being written — this stage alone produces a correctly-labelled, schema-valid, reasonably diverse dataset with **$0 spend**.

Run it: `python datagen/generate.py --split train --n 30000 --seed 1 --out datagen/output/train.jsonl` (val: `--n 1500 --seed 2`, test: `--n 1500 --seed 999`).

**Held-out test config (PRD §3.5's "disjoint vendors, agent names... no template overlap with train"):** `vendor_pools.vendor_pool_for_split()` reserves the last ~25% (min 1) of each category's vendor list, and the last of the four sample wallet addresses, exclusively for `val`/`test` — train never draws from them. `agent_id` includes the split name (`agt_{category}_{split}`), so it's disjoint by construction too. Verified on the current generated data: zero agent-id overlap between train and test; the only vendor strings shared are generic placeholders (`corrupt`, the garbled-payment marker; `counterparty_wallet`, a display label for chain hard negatives, not the actual identifying `counterparty_address`) and `base_network` (a rail label, not a distinguishing vendor identity — every `network_gas_fees` record uses it).

**Stage B — optional Claude enrichment (`enrich.py`, costs API credit).** Paraphrases only `activity.intent` and `output.reason` for lexical diversity on top of Stage A's output. It structurally cannot touch verdict/category/anomalies/amounts/vendors — those aren't in its output schema — and a numeric-preservation check (every number in the original text must survive the rewrite) provides a second safety net per item; anything that fails falls back to the deterministic text rather than being dropped.

Run it (cost-controlled): `python datagen/enrich.py --in datagen/output/test.jsonl --out datagen/output/test.enriched.jsonl --limit 20`

Measured cost (2026-08-26, `claude-sonnet-5`, intro pricing through 2026-08-31): **~$0.94 per 1,000 examples synchronously** → ~$31 for the full 30k/1.5k/1.5k = 33k split, a bit over the PRD's ~€20 datagen budget. Two ways to bring it under budget: switch to `--model claude-haiku-4-5` (materially cheaper, still preserves facts via the same safety net), or move the full run to the Batch API (50% off, documented but not yet wired into `enrich.py`). **Full-run enrichment has not been executed yet — pending an explicit go-ahead given the cost.**

## Phase 1 acceptance (PRD §7)

- [x] Protocol templates (x402/ap2/acp/stripe)
- [x] Generator with label-first construction
- [x] Distribution + hard-negative quotas enforced — see `MANIFEST.json` for the exact numbers on the generated data (currently: 55/30/10/5 bucket split matched, ~14.3-14.8% hard negatives per split, every category ≥300 and every anomaly ≥600 in train — full margin above the §3.5 minimums)
- [x] 30k/1.5k/1.5k generated (`datagen/output/{train,val,test}.jsonl`, gitignored — regenerate via `generate.py` with the seeds in `MANIFEST.json`)
- [x] Test-set hash printed — see `MANIFEST.json` (tracked in git; the data itself is not, so the hash is the durable record)
- [x] QA sampling CLI (`qa_sample.py`) — generates the 300-example sample and a review-log template
- [ ] **The actual 300-sample human review is a manual task, not done yet.** `datagen/output/qa_sample_300.jsonl` (sample, gitignored) and `datagen/qa_review_log.md` (tracked template) are ready for it.
- [ ] Realism check against ~100 real x402 settlements (manual, not started)
- [ ] Stage B (Claude enrichment) has not been run at scale — see cost numbers above; owner chose the free Stage-A-only path for now

Needs `ANTHROPIC_API_KEY` for Stage B only (see root `.env.example` / `.env`); Stage A needs nothing.

Hard boundary (mirrors Appendix A.3.3's rule for Oluso): this directory generates *labelled detection examples*, never a general-purpose "fake receipt" tool — label-first, spec-grounded, and reviewed.
