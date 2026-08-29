#!/usr/bin/env python3
"""QA sampling CLI (PRD §3.5: "hand-review a random 300 of train; fix
systematic generator errors at the pattern level, regenerate; re-review 100").

Pulls a reproducible random sample from a generated split and writes it next
to a review log template. The actual review is a human task — this script
only prepares the sample and the place to record findings.

Usage:
  python datagen/qa_sample.py --in datagen/output/train.jsonl --n 300 --seed 0 \
      --out datagen/output/qa_sample_300.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

REVIEW_LOG_TEMPLATE = """# QA review log — {sample_name}

Sampled {n} examples from `{source}` (seed {seed}) on {date_placeholder}.

Instructions: read each example in `{out_name}`, check the `output` verdict/category/anomalies/reason
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
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--log", default=None, help="path for the review log template (default: alongside --out)")
    args = ap.parse_args()

    examples = [json.loads(line) for line in Path(args.inp).open()]
    rng = random.Random(args.seed)
    sample = rng.sample(examples, min(args.n, len(examples)))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        for ex in sample:
            f.write(json.dumps(ex) + "\n")

    log_path = Path(args.log) if args.log else out_path.with_suffix(".review.md")
    if not log_path.exists():
        log_path.write_text(
            REVIEW_LOG_TEMPLATE.format(
                sample_name=out_path.stem,
                n=len(sample),
                source=args.inp,
                seed=args.seed,
                date_placeholder="<fill in review date>",
                out_name=out_path.name,
            )
        )
        print(f"Wrote review log template: {log_path}")
    else:
        print(f"Review log already exists, left untouched: {log_path}")

    print(f"Wrote {len(sample)} examples to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
