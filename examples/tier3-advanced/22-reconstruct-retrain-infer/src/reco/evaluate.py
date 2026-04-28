"""Evaluation harness: compute accuracy, F1, confusion matrix."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from datasets import load_dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline

from . import config


def run(ckpt_dir: Path | str, split: str = "test") -> dict[str, Any]:
    import os
    token = os.environ.get("HF_TOKEN") or None

    ckpt = Path(ckpt_dir)
    tokenizer = AutoTokenizer.from_pretrained(str(ckpt), token=token)
    model = AutoModelForSequenceClassification.from_pretrained(str(ckpt), token=token)

    clf = pipeline("text-classification", model=model, tokenizer=tokenizer,
                   device=0 if _has_gpu() else -1)

    ds = load_dataset(config.dataset_id(), split=split, token=token)
    preds, labels = [], []
    for row in ds:
        out = clf(row["text"], truncation=True, max_length=config.max_seq_len())[0]
        label_str = out["label"]
        preds.append(_label_to_int(label_str, model.config.id2label))
        labels.append(int(row["label"]))

    from sklearn.metrics import accuracy_score, f1_score, confusion_matrix
    report = {
        "ckpt":       str(ckpt),
        "split":      split,
        "n":          len(labels),
        "accuracy":   float(accuracy_score(labels, preds)),
        "f1_macro":   float(f1_score(labels, preds, average="macro")),
        "confusion":  confusion_matrix(labels, preds).tolist(),
    }
    out_path = config.ensure_results_dir() / "eval_report.json"
    out_path.write_text(json.dumps(report, indent=2))
    return report


def _has_gpu() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def _label_to_int(label_str: str, id2label: dict) -> int:
    # id2label maps int -> str; we need the inverse
    for idx, name in id2label.items():
        if name == label_str:
            return int(idx)
    # Fallback: try parsing 'LABEL_N'
    if label_str.startswith("LABEL_"):
        return int(label_str.split("_")[1])
    return -1
