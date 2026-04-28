"""Local files under $DATA_DIR."""
from __future__ import annotations

from pathlib import Path

from .. import config

NAME = "local"


def resolve(dataset: str | None = None) -> Path:
    root = config.data_dir()
    if dataset:
        return root / dataset
    return root
