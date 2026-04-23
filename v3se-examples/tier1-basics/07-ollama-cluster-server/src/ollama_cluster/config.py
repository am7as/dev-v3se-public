"""Path + env resolver. Same pattern as 01-foundation."""
from __future__ import annotations

import os
from pathlib import Path


def _env(key: str, default: str) -> str:
    v = os.environ.get(key, "")
    return v if v else default


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


def openai_model() -> str:
    return _env("OPENAI_MODEL", "gpt-4o-mini")


def openai_base_url() -> str | None:
    v = os.environ.get("OPENAI_BASE_URL", "")
    return v if v else None
