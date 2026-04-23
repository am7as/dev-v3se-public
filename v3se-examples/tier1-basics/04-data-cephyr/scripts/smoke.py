"""Smoke: verify paths + pandas import + sample data is reachable."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from data_cephyr import config, processing


def main() -> int:
    info = {
        "template": "data-cephyr",
        "data_dir": str(config.data_dir()),
        "results_dir": str(config.results_dir()),
        "dataset": config.dataset(),
    }

    # Look under $DATA_DIR/sample if that exists, else under $DATA_DIR directly.
    root = config.data_dir() / "sample"
    if not root.exists():
        root = config.data_dir()
    csvs = processing.list_csvs(root) if root.exists() else []
    info["data_root"] = str(root)
    info["csv_count"] = len(csvs)
    info["first_csv"] = str(csvs[0]) if csvs else None

    try:
        import pandas
        info["pandas"] = pandas.__version__
    except ImportError as e:
        info["pandas_error"] = str(e)
        print(json.dumps(info, indent=2))
        return 1

    print(json.dumps(info, indent=2))
    out = config.ensure_results_dir() / "smoke.json"
    out.write_text(json.dumps(info, indent=2))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
