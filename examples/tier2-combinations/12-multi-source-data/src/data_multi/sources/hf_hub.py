"""HuggingFace datasets — loaded via `datasets.load_dataset()`.

`resolve()` returns a Path to a cached dataset directory; the caller
uses `load()` to get a streaming or pandas dataset.
"""
from __future__ import annotations

import os
from pathlib import Path

NAME = "hf_hub"


def resolve(dataset: str | None = None) -> Path:
    """Return the HF cache dir; the real download lives under
    `HF_HOME/datasets/<dataset>/`."""
    hf_home = os.environ.get("HF_HOME", "/workspace/.hf-cache")
    return Path(hf_home) / "datasets"


def load(dataset: str, split: str = "train"):
    """Actually download + return a Hugging Face Dataset object."""
    from datasets import load_dataset
    token = os.environ.get("HF_TOKEN") or None
    return load_dataset(dataset, split=split, token=token)
