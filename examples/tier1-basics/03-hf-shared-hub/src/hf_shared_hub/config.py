"""Path + env resolver."""
from __future__ import annotations

import os
from pathlib import Path


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, "") or default


def data_dir() -> Path:
    return Path(_env("DATA_DIR", "/data"))


def results_dir() -> Path:
    return Path(_env("RESULTS_DIR", "/results"))


def models_dir() -> Path:
    return Path(_env("MODELS_DIR", "/models"))


def ensure_results_dir() -> Path:
    p = results_dir()
    p.mkdir(parents=True, exist_ok=True)
    return p


def hf_model_id() -> str:
    return _env("HF_MODEL", "google/gemma-2-2b-it")


def hf_model_snapshot() -> str | None:
    """Pre-downloaded snapshot path (takes precedence over HF_MODEL)."""
    v = _env("HF_MODEL_SNAPSHOT")
    return v or None


def device() -> str:
    return _env("HF_DEVICE", "auto")


def dtype() -> str:
    return _env("HF_DTYPE", "auto")


def max_new_tokens() -> int:
    return int(_env("HF_MAX_NEW_TOKENS", "200"))
