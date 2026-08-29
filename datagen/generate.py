#!/usr/bin/env python3
"""CLI: build plans for a split, render them deterministically (zero API
cost), validate every example, write JSONL, print a distribution report.

Usage:
  python datagen/generate.py --split test --n 50 --seed 0 --out datagen/output/test_sample.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from plan import build_plans, distribution_report  # noqa: E402
from render import render_plan  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True, choices=["train", "val", "test"])
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    plans = build_plans(args.split, args.n, seed=args.seed)
    report = distribution_report(plans)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    errors = 0
    with out_path.open("w") as f:
        for plan in plans:
            try:
                example = render_plan(plan, seed=args.seed)
            except Exception as e:
                errors += 1
                print(f"RENDER/VALIDATION ERROR [{plan.id}]: {e}", file=sys.stderr)
                continue
            f.write(example.model_dump_json(exclude_none=True) + "\n")

    print(f"Wrote {report['n'] - errors}/{report['n']} examples to {out_path}")
    if errors:
        print(f"  {errors} examples FAILED validation (see stderr) — not written")
    print(json.dumps(report, indent=2))

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
