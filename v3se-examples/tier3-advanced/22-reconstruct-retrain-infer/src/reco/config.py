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


def model_id() -> str:        return _env("HF_MODEL", "distilbert-base-uncased")
def model_snapshot() -> str | None:
    v = _env("HF_MODEL_SNAPSHOT")
    return v or None

def dataset_id() -> str:       return _env("HF_DATASET", "emotion")
def num_labels() -> int:       return int(_env("NUM_LABELS", "6"))
def num_epochs() -> int:       return int(_env("NUM_EPOCHS", "3"))
def per_device_batch() -> int: return int(_env("PER_DEVICE_BATCH", "16"))
def grad_accum() -> int:       return int(_env("GRAD_ACCUM", "1"))
def learning_rate() -> float:  return float(_env("LEARNING_RATE", "2e-5"))
def max_seq_len() -> int:      return int(_env("MAX_SEQ_LEN", "128"))
def surgery_config_path() -> str: return _env("SURGERY_CONFIG", "configs/surgery.yaml")
