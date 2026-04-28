"""Central path + env resolver.

All other modules go through here — never read env vars or compute paths
inline. Matches the pattern used in the llm-safety-analysis reference
project.
"""
from __future__ import annotations

import os
from pathlib import Path


def _env(key: str, default: str) -> str:
    value = os.environ.get(key, "")
    return value if value else default


def data_dir() -> Path:
    """Where datasets and inputs live. Defaults to /data inside the container."""
    return Path(_env("DATA_DIR", "/data"))


def results_dir() -> Path:
    """Where outputs go. Defaults to /results."""
    return Path(_env("RESULTS_DIR", "/results"))


def models_dir() -> Path:
    """Where model weights live. Defaults to /models."""
    return Path(_env("MODELS_DIR", "/models"))


def workspace_dir() -> Path:
    """Project root inside the container. Defaults to /workspace."""
    return Path(_env("WORKSPACE_DIR", "/workspace"))


def ensure_results_dir() -> Path:
    """Create RESULTS_DIR if missing, return it."""
    p = results_dir()
    p.mkdir(parents=True, exist_ok=True)
    return p
