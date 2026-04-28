"""Architecture-surgery operations.

Current implementations:
    - replace_classification_head: swap the existing classification/LM head
      with a fresh one of shape (hidden_size, num_labels). For turning an
      LLM into a classifier, or re-initializing a BERT head for a new task.

Extension points:
    - add a regression head
    - freeze/unfreeze by layer index
    - insert adapter modules into specific transformer blocks
    - swap attention implementation

Each operation takes a pretrained HF model, mutates it in-place (or wraps
it), saves the result under $RESULTS_DIR/surgeried/<ts>/, and records what
was done in surgery_summary.json.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
from pathlib import Path
from typing import Any

import torch
import yaml
from torch import nn
from transformers import AutoModel, AutoModelForSequenceClassification, AutoTokenizer

from . import config


def _ts() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _read_surgery_config(path: Path | None = None) -> dict[str, Any]:
    p = path or Path(config.surgery_config_path())
    if not p.is_absolute():
        p = Path("/workspace") / p
        if not p.exists():
            p = Path.cwd() / config.surgery_config_path()
    return yaml.safe_load(p.read_text())


def replace_classification_head(base_model_id: str, num_labels: int, out_dir: Path,
                                freeze_base: bool = False) -> dict[str, Any]:
    """Load a backbone, attach a fresh classification head, save the result."""
    token = os.environ.get("HF_TOKEN") or None
    tokenizer = AutoTokenizer.from_pretrained(base_model_id, token=token)
    # AutoModelForSequenceClassification with num_labels auto-constructs a
    # new classification head on top of the backbone.
    model = AutoModelForSequenceClassification.from_pretrained(
        base_model_id, num_labels=num_labels, token=token,
        # Ignore size mismatch on the head — we're replacing it anyway.
        ignore_mismatched_sizes=True,
    )

    if freeze_base:
        for name, p in model.named_parameters():
            if "classifier" not in name:
                p.requires_grad = False

    out_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))

    return {
        "operation":        "replace_classification_head",
        "base_model":       base_model_id,
        "num_labels":       num_labels,
        "freeze_base":      freeze_base,
        "trainable_params": int(sum(p.numel() for p in model.parameters() if p.requires_grad)),
        "total_params":     int(sum(p.numel() for p in model.parameters())),
        "out_dir":          str(out_dir),
    }


def run(out_dir: Path | None = None) -> dict[str, Any]:
    surgery = _read_surgery_config()
    op = surgery.get("operation", "replace_classification_head")
    out_dir = out_dir or (config.ensure_results_dir() / "surgeried" / _ts())

    base = config.model_snapshot() or config.model_id()

    if op == "replace_classification_head":
        summary = replace_classification_head(
            base_model_id=base,
            num_labels=int(surgery.get("num_labels", config.num_labels())),
            out_dir=out_dir,
            freeze_base=bool(surgery.get("freeze_base", False)),
        )
    else:
        raise NotImplementedError(
            f"Surgery operation '{op}' not implemented. Add a handler in src/reco/surgery.py."
        )

    (out_dir / "surgery_summary.json").write_text(json.dumps(summary, indent=2))
    return summary
