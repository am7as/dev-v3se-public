"""Load a HuggingFace model baked into a SIF at `/opt/model`.

This example builds an Apptainer SIF whose `%post` section downloads
the weights from HuggingFace ONCE, at build time, and bundles them
inside the `.sif`. At run time the model is loaded from a fixed local
path — no Hub access, no Cephyr / Mimer cache at run time.

The SIF is portable: build it on laptop or on Alvis, run it on
either. One file = quota-safe on Cephyr.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, PreTrainedModel, PreTrainedTokenizer

from . import config

# Where the build step bakes the weights. Overridable via env for
# local dev against a pre-downloaded directory.
MODEL_DIR = Path(os.environ.get("MODEL_DIR", "/opt/model"))


def _resolve_source() -> str:
    if not MODEL_DIR.exists():
        raise RuntimeError(
            f"MODEL_DIR={MODEL_DIR} not found. "
            "This example expects a SIF with weights baked in. "
            "Build it first: bash scripts/build-model-sif.sh"
        )
    return str(MODEL_DIR)


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
