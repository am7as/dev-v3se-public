"""Load a HuggingFace model + tokenizer with C3SE-aware defaults.

Precedence for "where do I get the weights from":
    1. HF_MODEL_SNAPSHOT — a local path (e.g. on /mimer on Alvis)
    2. HF_MODEL — downloaded into HF_HOME on first call
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, PreTrainedModel, PreTrainedTokenizer

from . import config


def _resolve_source() -> str:
    snap = config.hf_model_snapshot()
    return snap if snap else config.hf_model_id()


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
    token = os.environ.get("HF_TOKEN") or None

    tokenizer = AutoTokenizer.from_pretrained(source, token=token)
    model = AutoModelForCausalLM.from_pretrained(
        source,
        torch_dtype=dtype,
        device_map=dev if dev != "cpu" else None,
        token=token,
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
    # Strip the echoed prompt for cleaner output.
    if text.startswith(prompt):
        text = text[len(prompt):].lstrip()
    return {
        "text":   text,
        "model":  _resolve_source(),
        "device": dev,
        "usage":  {"input_tokens":  int(inputs["input_ids"].numel()),
                   "output_tokens": int(out_ids.numel() - inputs["input_ids"].numel())},
    }
