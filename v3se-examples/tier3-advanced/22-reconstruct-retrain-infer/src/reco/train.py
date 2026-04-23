"""Retrain a surgeried model using HF Trainer.

The surgery has already produced a model with the right head; this just
fine-tunes it on the target task's dataset.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
from datasets import load_dataset
from transformers import (
    AutoModelForSequenceClassification, AutoTokenizer, DataCollatorWithPadding,
    Trainer, TrainingArguments,
)

from . import config


def _ts() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _metrics(eval_pred):
    from sklearn.metrics import accuracy_score, f1_score
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy_score(labels, preds),
        "f1_macro": f1_score(labels, preds, average="macro"),
    }


def run(surgeried_dir: Path | str) -> dict[str, Any]:
    token = os.environ.get("HF_TOKEN") or None
    surgeried = Path(surgeried_dir)
    run_id = _ts()
    out_dir = config.ensure_results_dir() / "checkpoints" / run_id

    tokenizer = AutoTokenizer.from_pretrained(str(surgeried), token=token)
    model = AutoModelForSequenceClassification.from_pretrained(str(surgeried), token=token)

    ds = load_dataset(config.dataset_id(), token=token)

    def tok_fn(batch):
        return tokenizer(batch["text"], truncation=True, max_length=config.max_seq_len())

    ds_tok = ds.map(tok_fn, batched=True)

    args = TrainingArguments(
        output_dir=str(out_dir),
        num_train_epochs=config.num_epochs(),
        per_device_train_batch_size=config.per_device_batch(),
        per_device_eval_batch_size=config.per_device_batch(),
        gradient_accumulation_steps=config.grad_accum(),
        learning_rate=config.learning_rate(),
        logging_steps=20,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,
        bf16=True,
        report_to=["wandb"] if os.environ.get("WANDB_API_KEY") else [],
    )
    trainer = Trainer(
        model=model, args=args, tokenizer=tokenizer,
        train_dataset=ds_tok["train"],
        eval_dataset=ds_tok.get("validation", ds_tok.get("test")),
        data_collator=DataCollatorWithPadding(tokenizer),
        compute_metrics=_metrics,
    )
    train_result = trainer.train()
    trainer.save_model(str(out_dir))

    summary = {
        "run_id":       run_id,
        "ckpt_dir":     str(out_dir),
        "surgeried":    str(surgeried),
        "dataset":      config.dataset_id(),
        "train_loss":   float(train_result.training_loss),
        "epochs":       config.num_epochs(),
    }
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2))
    return summary
