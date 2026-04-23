"""Load a HuggingFace model from C3SE's pre-downloaded shared hub.

This example is **cluster-oriented** — the model comes from the
read-only `/mimer/NOBACKUP/Datasets/LLM/huggingface/hub/` mirror that
C3SE maintains. Zero download, zero quota impact.

HF_MODEL_SNAPSHOT must be set to a concrete snapshot directory:

    /mimer/NOBACKUP/Datasets/LLM/huggingface/hub/models--<org>--<name>/snapshots/<hash>/

There is deliberately NO fallback to Hub streaming — if the model
C3SE mirrors doesn't match your needs, use 08-hf-sif-bundle (bake
your own) or 09-hf-hub-streaming (download on demand).
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, PreTrainedModel, PreTrainedTokenizer

from . import config


def _resolve_source() -> str:
    snap = config.hf_model_snapshot()
    if not snap:
        raise RuntimeError(
            "HF_MODEL_SNAPSHOT is not set. This example loads from C3SE's "
            "shared hub only. Set HF_MODEL_SNAPSHOT in .env, e.g. "
            "/mimer/NOBACKUP/Datasets/LLM/huggingface/hub/models--<org>--<name>/snapshots/<hash>/"
        )
    if not Path(snap).exists():
        raise RuntimeError(
            f"HF_MODEL_SNAPSHOT={snap} does not exist. "
            "List the available snapshots with: ls /mimer/NOBACKUP/Datasets/LLM/huggingface/hub/"
        )
    return snap


def _resolve_device() -> str:
    d = config.device()
    if d == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return d


def _resolve_dtype() -> torch.dtype | str:
    d = config.dtype()
    if d == "auto":
        return "auto"
    return {
        "bfloat16": torch.bfloat16,
        "float16":  torch.float16,
        "float32":  torch.float32,
    }[d]


@lru_cache(maxsize=1)
def load() -> tuple[PreTrainedModel, PreTrainedTokenizer, str]:
    source = _resolve_source()
    dev = _resolve_device()
    dtype = _resolve_dtype()

    tokenizer = AutoTokenizer.from_pretrained(source, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        source,
        torch_dtype=dtype,
        device_map=dev if dev != "cpu" else None,
        local_files_only=True,
    )
    if dev == "cpu":
        model = model.to("cpu")
    model.eval()
    return model, tokenizer, dev


def generate(prompt: str, *, max_new_tokens: int | None = None, **kw: Any) -> dict[str, Any]:
    model, tokenizer, dev = load()
    mnt = max_new_tokens if max_new_tokens is not None else config.max_new_tokens()
    inputs = tokenizer(prompt, return_tensors="pt").to(dev if dev != "cpu" else "cpu")
    with torch.no_grad():
        out_ids = model.generate(**inputs, max_new_tokens=mnt, do_sample=False, **kw)
    text = tokenizer.decode(out_ids[0], skip_special_tokens=True)
    if text.startswith(prompt):
        text = text[len(prompt):].lstrip()
    return {
        "text":   text,
        "model":  _resolve_source(),
        "device": dev,
        "usage":  {"input_tokens":  int(inputs["input_ids"].numel()),
                   "output_tokens": int(out_ids.numel() - inputs["input_ids"].numel())},
    }
