from __future__ import annotations

import os
from pathlib import Path


def _env(k: str, d: str = "") -> str:
    return os.environ.get(k, "") or d


def data_dir() -> Path:    return Path(_env("DATA_DIR", "/data"))
def results_dir() -> Path: return Path(_env("RESULTS_DIR", "/results"))


def ensure_results_dir() -> Path:
    p = results_dir()
    p.mkdir(parents=True, exist_ok=True)
    return p


def source() -> str:
    return _env("DATASET_SOURCE", "local")
