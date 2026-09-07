# bench — EleriBench, Phase 2

Public benchmark for agent-spend verification. See PRD §4, §7 Phase 2.

## What's built

- `test.jsonl` — the locked 1,500-example test set, copied verbatim from `../datagen/output/test.jsonl` (seed 999, held out per `../datagen/MANIFEST.json`: disjoint vendor pools, disjoint agent IDs from train — see `../datagen/README.md`). Apache 2.0, same as the rest of this repo — see [`LICENSE`](../LICENSE).
- `few_shot.py` — the fixed 10-example few-shot set every baseline sees, pulled from the hand-written `../schemas/examples/eleri_examples.json` (never from generated data, so it can't leak a test example).
- `prompting.py` — the one system prompt + few-shot conversation + output schema every baseline gets, identically (PRD §3.7: "identical prompt + 10 few-shot examples + same constrained-JSON schema").
- `_schemas.py` — reuses `../schemas/python/models.py`'s enums, plus `EleriVerdictLoose`: the same fields as `EleriVerdict` but without the match+blocking-anomaly business rule, since baselines being *scored* legitimately violate it sometimes — that's a real signal (`business_rule_violations` in each summary), not something to swallow as a parse failure.
- `runners/` — `AnthropicRunner` (`claude-haiku-4-5`, via `messages.parse` structured output) and `OpenAIRunner` (`gpt-4o-mini`, via `chat.completions` strict `json_schema`). Both registered in `runners/RUNNERS`.
- `pricing.py` — $/1M-token rates, checked 2026-08-26 (Haiku from the claude-api skill's cached table; GPT-4o-mini via live web search — $0.15/$0.60).
- `metrics.py` — verdict accuracy + macro-F1, category accuracy + macro-F1, per-anomaly multi-label P/R/F1 (micro + macro), 10-bin ECE, and the confidence-threshold-τ/coverage fit from PRD §3.7.
- `run_eval.py` — the one-command harness: `python bench/run_eval.py --model claude-haiku-4-5 [--limit N]`. Before scoring anything, hashes `--test` and checks it against `../datagen/MANIFEST.json`'s split hashes; refuses to run (no API calls made) on a mismatch unless `--skip-hash-check` is passed, and records the matched split (or lack of one) in the summary. Writes `results/<model>_predictions.jsonl` (raw, gitignored) and `results/<model>_summary.json` (tracked).
- `leaderboard.py` — reads every `results/*_summary.json` and writes `results/leaderboard.md`, including the §7 Phase 2 decision gate (flags if any baseline already clears 98% anomaly macro-F1).

Not built yet:
- **`test_ood.jsonl`** — the out-of-distribution slice (a receipt format that appears nowhere in training). Format definitions must live only in this directory's config namespace, never in `../datagen`, per PRD §4 — not started.
- **Qwen 2.5 base (few-shot) baseline.** `run_eval.py` is provider-agnostic by design (`runners/` is a small registry), so adding it is additive once there's an OpenAI-compatible endpoint to hit — either a hosted one (Together/Fireworks/OpenRouter, needs its own key) or local serving, which naturally falls out of Phase 3/4's GPU work. Deferred rather than blocking the two frontier baselines.

## Running it

```bash
export ANTHROPIC_API_KEY=... OPENAI_API_KEY=...   # or `set -a; source ../.env; set +a`
python bench/run_eval.py --model claude-haiku-4-5   # full 1,500-example run
python bench/run_eval.py --model gpt-4o-mini
python bench/leaderboard.py
```

## Results (2026-08-27, full 1,500-example test set, rerun after the datagen fixes below)

Full table: [`results/leaderboard.md`](results/leaderboard.md). Headline numbers:

| model | verdict acc | category acc | anomaly macro-F1 | ECE | cost / 1k audits |
|---|---|---|---|---|---|
| claude-haiku-4-5 | 0.808 | 0.981 | 0.684 | 0.128 | $5.26 |
| gpt-4o-mini | 0.682 | 0.955 | 0.392 | 0.240 | $0.60 |

**Rerun context:** the first pass (2026-08-26) used a `test.jsonl` that turned out to have a real label-noise bug — `Ctx.currency` in `../datagen/render.py` randomized EUR 20% of the time regardless of anomaly, leaking unlabeled currency mismatches into ~10% of every split (train/val/test alike), plus two other datagen bugs (unlearnable `duplicate_charge`, noisy `purpose_mismatch` pairing) — found while diagnosing why the first trained Eleri checkpoint underperformed on exactly those three anomalies. All three are fixed (see `../datagen/README.md` and `../datagen/MANIFEST.json`'s `notes` field for the full postmortem), and train/val/test were regenerated. Both baselines were rerun on the corrected test set; this table is those rerun numbers. The first pass's predictions and summaries weren't kept, so the pre-fix numbers aren't reproduced here.

Actual spend: **$7.89 (Haiku) + $0.91 (GPT-4o-mini) = $8.80** for this rerun (on top of the first pass's $8.80). No prompt caching used, so this is the cost ceiling, not the floor. Zero parse failures and at most 1 business-rule violation across 1,500 examples per baseline.

**Decision gate (PRD §7 Phase 2 acceptance):** neither baseline clears 98% anomaly macro-F1 (best: Haiku at 0.684) — gate does not trigger, proceed to Phase 3 (fine-tune) as planned. `stale_settlement` and `wrong_network_or_token` are now the hardest anomalies for GPT-4o-mini (F1 ≈ 0); `settlement_not_found` is the easiest (F1 ≥ 0.97 for both).
