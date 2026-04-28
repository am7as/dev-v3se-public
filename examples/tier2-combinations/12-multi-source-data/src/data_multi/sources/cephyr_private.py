"""Cephyr private area. Mounted into /data by the sbatch bind.

From inside the container, indistinguishable from `local` — the work
happens in the sbatch's --bind flag, not in Python.
"""
from __future__ import annotations

from pathlib import Path

from .. import config

NAME = "cephyr_private"


def resolve(dataset: str | None = None) -> Path:
    root = config.data_dir()
    if dataset:
        return root / dataset
    return root
