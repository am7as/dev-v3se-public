from __future__ import annotations

import argparse
import json
import sys

from reco.evaluate import run


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--split", default="test")
    args = ap.parse_args(argv)
    report = run(args.ckpt, split=args.split)
    print(json.dumps({k: v for k, v in report.items() if k != "confusion"}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
