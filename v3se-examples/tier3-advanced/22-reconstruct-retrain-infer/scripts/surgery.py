"""Reconstruct (modify architecture) a pretrained model per configs/surgery.yaml."""
from __future__ import annotations

import json
import sys

from reco.surgery import run


def main() -> int:
    summary = run()
    print(json.dumps(summary, indent=2))
    print(f"\nModified model saved to: {summary['out_dir']}")
    print(f"Next: sbatch --export=ALL,MODEL='{summary['out_dir']}' slurm/train.sbatch")
    return 0


if __name__ == "__main__":
    sys.exit(main())
