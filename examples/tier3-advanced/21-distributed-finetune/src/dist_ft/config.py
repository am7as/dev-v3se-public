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


def model_id() -> str:        return _env("HF_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
def model_snapshot() -> str | None:
    v = _env("HF_MODEL_SNAPSHOT")
    return v or None

def dataset_id() -> str:       return _env("HF_DATASET", "tatsu-lab/alpaca")
def dataset_split() -> str:    return _env("HF_DATASET_SPLIT", "train")
def num_epochs() -> int:       return int(_env("NUM_EPOCHS", "1"))
def per_device_batch() -> int: return int(_env("PER_DEVICE_BATCH", "4"))
def grad_accum() -> int:       return int(_env("GRAD_ACCUM", "8"))
def learning_rate() -> float:  return float(_env("LEARNING_RATE", "2e-5"))
def max_seq_len() -> int:      return int(_env("MAX_SEQ_LEN", "2048"))
def warmup_ratio() -> float:   return float(_env("WARMUP_RATIO", "0.03"))
def save_steps() -> int:       return int(_env("SAVE_STEPS", "500"))
def save_total_limit() -> int: return int(_env("SAVE_TOTAL_LIMIT", "3"))
