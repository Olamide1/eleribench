# QA review log — qa_sample_300

Sampled 300 examples from `datagen/output/train.jsonl` (seed 0) on <fill in review date>.

Instructions: read each example in `qa_sample_300.jsonl`, check the `output` verdict/category/anomalies/reason
against the `input`. Log every disagreement below with the example `id`, what's wrong, and whether it's
a one-off or a systematic generator bug (mutator logic in `render.py`, a vendor/purpose pool entry in
`vendor_pools.py`, etc.). Systematic bugs should be fixed in the generator and this split regenerated,
not hand-patched in the data.

| id | issue | one-off or systematic? | fixed? |
|---|---|---|---|
| | | | |

## Summary

- Examples reviewed:
- Disagreements found:
- Systematic issues found (and where fixed):
