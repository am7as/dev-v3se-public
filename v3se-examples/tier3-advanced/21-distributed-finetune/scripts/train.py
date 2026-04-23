"""Distributed training entry point.

Launched by `pixi run train`, which wraps this in `accelerate launch
--config_file configs/accelerate/<strategy>.yaml`.
"""
from __future__ import annotations

import sys

from dist_ft.train import run


def main() -> int:
    summary = run()
    # Only rank 0 prints
    import os
    if int(os.environ.get("RANK", "0")) == 0:
        import json
        print(json.dumps(summary, indent=2))
        print(f"\nCheckpoints: {summary['ckpt_dir']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
