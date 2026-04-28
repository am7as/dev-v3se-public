"""LoRA finetune with optional WandB + MLflow logging.

Nearly identical to 05-train-lora, plus experiment-tracking hooks.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
from pathlib import Path
from typing import Any

import torch
from datasets import Dataset, load_dataset
from peft import LoraConfig, TaskType, get_peft_model
from transformers import (
    AutoModelForCausalLM, AutoTokenizer,
    DataCollatorForLanguageModeling, Trainer, TrainingArguments,
)

from . import config


_DEFAULT = [
    {"text": "The weather today is bright and clear."},
    {"text": "Neural networks learn patterns from data."},
    {"text": "Chalmers is located in Gothenburg, Sweden."},
    {"text": "Gradient descent iteratively minimizes loss."},
    {"text": "Alvis is a GPU cluster operated by C3SE."},
]


def _ts() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _load() -> Dataset:
    ds_id = config.dataset_id()
    if not ds_id:
        return Dataset.from_list(_DEFAULT)
    if os.path.isfile(ds_id):
        return load_dataset("json", data_files=ds_id, split="train")
    return load_dataset(ds_id, split="train")


def _source() -> str:
    return config.model_snapshot() or config.model_id()


def _report_to() -> list[str]:
    r = []
    if os.environ.get("WANDB_API_KEY"):
        r.append("wandb")
    if os.environ.get("MLFLOW_TRACKING_URI"):
        r.append("mlflow")
    return r


def run(out_dir: Path | None = None) -> dict[str, Any]:
    source = _source()
    out_dir = out_dir or (config.ensure_results_dir() / "adapters" / _ts())
    out_dir.mkdir(parents=True, exist_ok=True)

    token = os.environ.get("HF_TOKEN") or None
    tokenizer = AutoTokenizer.from_pretrained(source, token=token)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    base = AutoModelForCausalLM.from_pretrained(source, token=token)
    lora_cfg = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=config.lora_r(),
        lora_alpha=config.lora_alpha(),
        lora_dropout=config.lora_dropout(),
        bias="none",
    )
    model = get_peft_model(base, lora_cfg)

    ds = _load()
    ds_tok = ds.map(
        lambda examples: tokenizer(
            examples["text"], truncation=True, padding="max_length", max_length=128
        ),
        batched=True, remove_columns=ds.column_names,
    )

    args = TrainingArguments(
        output_dir=str(out_dir / "trainer"),
        num_train_epochs=config.num_epochs(),
        per_device_train_batch_size=config.batch_size(),
        learning_rate=config.learning_rate(),
        logging_steps=1,
        save_strategy="no",
        report_to=_report_to(),
        fp16=torch.cuda.is_available(),
    )
    collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)
    trainer = Trainer(model=model, args=args, train_dataset=ds_tok, data_collator=collator)
    trainer.train()

    model.save_pretrained(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))

    summary = {
        "adapter_dir":      str(out_dir),
        "base_model":       source,
        "trainable_params": int(sum(p.numel() for p in model.parameters() if p.requires_grad)),
        "epochs":           config.num_epochs(),
        "lora_r":           config.lora_r(),
        "dataset_rows":     len(ds),
        "logged_to":        _report_to(),
    }
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2))
    return summary
