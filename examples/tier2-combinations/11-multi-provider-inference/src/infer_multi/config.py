from __future__ import annotations

import os
from pathlib import Path


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, "") or default


def data_dir() -> Path:    return Path(_env("DATA_DIR", "/data"))
def results_dir() -> Path: return Path(_env("RESULTS_DIR", "/results"))


def ensure_results_dir() -> Path:
    p = results_dir()
    p.mkdir(parents=True, exist_ok=True)
    return p


def default_provider() -> str:
    return _env("DEFAULT_PROVIDER", "openai")
