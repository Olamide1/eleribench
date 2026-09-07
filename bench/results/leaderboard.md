# EleriBench leaderboard

Test set: `bench/test.jsonl`, n=1500 (see `../datagen/MANIFEST.json` for the sha256 hash and generation seed).

| model | verdict acc | verdict macro-F1 | category acc | anomaly macro-F1 | anomaly micro-F1 | ECE (10-bin) | parse failures | cost / 1k audits |
|---|---|---|---|---|---|---|---|---|
| eleri-1.5b | 0.972 | 0.921 | 0.972 | 0.989 | 0.989 | 0.050 | 42/1500 | $0.6159 |
| claude-haiku-4-5 | 0.808 | 0.783 | 0.981 | 0.684 | 0.662 | 0.128 | 0/1500 | $5.2587 |
| gpt-4o-mini | 0.682 | 0.692 | 0.955 | 0.392 | 0.404 | 0.240 | 0/1500 | $0.6037 |

## Per-anomaly F1 (hardest anomalies called out per PRD §3.7)

| anomaly | eleri-1.5b | claude-haiku-4-5 | gpt-4o-mini |
|---|---|---|---|
| address_poisoning_lookalike | 1.000 | 0.971 | 0.455 |
| amount_discrepancy | 1.000 | 0.850 | 0.170 |
| amount_exceeds_mandate | 0.969 | 0.907 | 0.578 |
| budget_period_at_risk | 0.989 | 0.722 | 0.704 |
| currency_mismatch | 0.989 | 0.889 | 0.989 |
| duplicate_charge | 1.000 | 0.453 | 0.033 |
| mandate_expired | 0.991 | 0.372 | 0.215 |
| no_matching_mandate | 0.990 | 0.462 | 0.048 |
| purpose_mismatch | 0.983 | 0.417 | 0.352 |
| settlement_not_found | 0.991 | 1.000 | 0.972 |
| split_transaction_pattern | 0.991 | 0.825 | 0.161 |
| stale_settlement | 1.000 | 0.068 | 0.000 |
| velocity_anomaly | 0.990 | 0.881 | 0.462 |
| vendor_not_allowed | 0.962 | 0.935 | 0.742 |
| wrong_network_or_token | 0.990 | 0.507 | 0.000 |

## Decision gate (PRD §7 Phase 2 acceptance)

No baseline hit the 98% anomaly-F1 gate (best: claude-haiku-4-5 at 0.684). Proceed to Phase 3 (fine-tune) as planned.
