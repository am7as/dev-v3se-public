"""Path + training-hyperparam env resolver."""
from __future__ import annotations

import os
from pathlib import Path


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, "") or default


def data_dir() -> Path:
    return Path(_env("DATA_DIR", "/data"))


def results_dir() -> Path:
    return Path(_env("RESULTS_DIR", "/results"))


def ensure_results_dir() -> Path:
    p = results_dir()
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------- training knobs ----------
def model_id() -> str:
    return _env("HF_MODEL", "sshleifer/tiny-gpt2")


def model_snapshot() -> str | None:
    v = _env("HF_MODEL_SNAPSHOT")
    return v or None


def dataset_id() -> str:
    """Empty = use built-in in-memory tiny sample."""
    return _env("HF_DATASET")


def lora_r() -> int:
    return int(_env("LORA_R", "8"))


def lora_alpha() -> int:
    return int(_env("LORA_ALPHA", "16"))


def lora_dropout() -> float:
    return float(_env("LORA_DROPOUT", "0.05"))


def num_epochs() -> int:
    return int(_env("NUM_EPOCHS", "1"))


def batch_size() -> int:
    return int(_env("BATCH_SIZE", "4"))


def learning_rate() -> float:
    return float(_env("LEARNING_RATE", "1e-4"))
