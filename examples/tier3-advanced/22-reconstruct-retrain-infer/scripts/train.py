"""Retrain a surgeried model on the target task.

    accelerate launch --config_file configs/accelerate/${ACCELERATE_CONFIG:-single}.yaml scripts/train.py --model <dir>
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from reco.train import run


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.environ.get("MODEL"),
                    help="Path to the surgeried model directory.")
    args = ap.parse_args(argv)
    if not args.model:
        print("Pass --model or set MODEL env var.", file=sys.stderr)
        return 2

    summary = run(args.model)
    if int(os.environ.get("RANK", "0")) == 0:
        print(json.dumps(summary, indent=2))
        print(f"\nCheckpoint: {summary['ckpt_dir']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
