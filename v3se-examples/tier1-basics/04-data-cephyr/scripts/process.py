"""Process CSVs under $DATA_DIR/<source>/ and write a summary JSON.

    pixi run process --source sample
    pixi run process --source private
"""
from __future__ import annotations

import argparse
import sys

from data_cephyr import config, processing


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=None,
                    help="Subfolder under $DATA_DIR. Defaults to .env's DATASET, "
                         "or 'sample' if unset.")
    ap.add_argument("--out", default=None,
                    help="Output JSON path (relative to $RESULTS_DIR by default).")
    args = ap.parse_args(argv)

    source_name = args.source or config.dataset()
    source_dir  = config.data_dir() / source_name
    if not source_dir.exists():
        # Fallback: $DATA_DIR directly (for raw sbatch binds)
        source_dir = config.data_dir()

    out_name = args.out or "summary.json"
    out_path = config.ensure_results_dir() / out_name

    print(f"reading from : {source_dir}")
    print(f"writing to   : {out_path}")

    result = processing.process(source_dir, out_path)
    print(f"files        : {result['file_count']}")
    print(f"total rows   : {result['total_rows']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
