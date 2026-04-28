"""Bundle an adapter + base-model reference into a self-contained SIF.

    pixi run bundle --adapter-dir /results/adapters/<ts>
"""
from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path

from train_infer import config
from train_infer.bundler import build


def _ts() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter-dir", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=None,
                    help="Output SIF path. Defaults to $RESULTS_DIR/bundles/<ts>.sif")
    ap.add_argument("--base-model", default=None,
                    help="Override HF_MODEL for this bundle.")
    args = ap.parse_args(argv)

    base = args.base_model or config.model_id()
    out = args.out or (config.ensure_results_dir() / "bundles" / f"{_ts()}.sif")
    build(args.adapter_dir, base, out)
    print(f"Bundled: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
