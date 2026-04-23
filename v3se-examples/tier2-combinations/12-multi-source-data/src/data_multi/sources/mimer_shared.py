"""Cephyr shared area (/mimer/NOBACKUP/Datasets/). Read-only.

The sbatch binds a specific shared dataset over /data:ro. Python code
treats it the same as any local path.
"""
from __future__ import annotations

from pathlib import Path

from .. import config

NAME = "mimer_shared"


def resolve(dataset: str | None = None) -> Path:
    root = config.data_dir()
    if dataset:
        return root / dataset
    return root
