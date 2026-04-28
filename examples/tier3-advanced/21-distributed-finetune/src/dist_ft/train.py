"""Distributed full-parameter finetune using TRL's SFTTrainer.

Launched via `accelerate launch --config_file configs/accelerate/<cfg>.yaml
scripts/train.py`. `accelerate` handles DeepSpeed / FSDP orchestration;
we just write the training loop as if it were single-GPU code.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
from pathlib import Path
from typing import Any

import torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import SFTConfig, SFTTrainer

from . import config


def _ts() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _source() -> str:
    return config.model_snapshot() or config.model_id()


def _format_row(row: dict) -> str:
    """Alpaca-style formatter — customize for your dataset schema."""
    if "instruction" in row and "output" in row:
        ctx = row.get("input", "")
        if ctx:
            return (
                f"### Instruction:\n{row['instruction']}\n\n"
                f"### Input:\n{ctx}\n\n"
                f"### Response:\n{row['output']}"
            )
        return (
            f"### Instruction:\n{row['instruction']}\n\n"
            f"### Response:\n{row['output']}"
        )
    return row.get("text", "")


def run() -> dict[str, Any]:
    source = _source()
    token = os.environ.get("HF_TOKEN") or None
    run_id = _ts()
    out_dir = config.ensure_results_dir() / "checkpoints" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(source, token=token)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        source, token=token, torch_dtype=torch.bfloat16,
    )

    ds = load_dataset(config.dataset_id(), split=config.dataset_split(), token=token)
    ds = ds.map(lambda r: {"text": _format_row(r)})

    report = ["wandb"] if os.environ.get("WANDB_API_KEY") else []

    sft = SFTConfig(
        output_dir=str(out_dir),
        num_train_epochs=config.num_epochs(),
        per_device_train_batch_size=config.per_device_batch(),
        gradient_accumulation_steps=config.grad_accum(),
        learning_rate=config.learning_rate(),
        warmup_ratio=config.warmup_ratio(),
        max_seq_length=config.max_seq_len(),
        logging_steps=10,
        save_strategy="steps",
        save_steps=config.save_steps(),
        save_total_limit=config.save_total_limit(),
        bf16=True,
        dataset_text_field="text",
        report_to=report,
        gradient_checkpointing=True,
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=ds,
        args=sft,
    )
    trainer.train()
    trainer.save_model(str(out_dir))

    summary = {
        "run_id":       run_id,
        "ckpt_dir":     str(out_dir),
        "base_model":   source,
        "dataset":      config.dataset_id(),
        "rows":         len(ds),
        "epochs":       config.num_epochs(),
        "effective_bs": config.per_device_batch() * config.grad_accum() *
                        int(os.environ.get("WORLD_SIZE", "1")),
    }
    if int(os.environ.get("RANK", "0")) == 0:
        (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2))
    return summary
