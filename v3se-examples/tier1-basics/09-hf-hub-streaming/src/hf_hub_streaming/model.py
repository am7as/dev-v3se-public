"""Stream a HuggingFace model from the Hub at first call.

Simplest pattern: call `from_pretrained(HF_MODEL)`, let `transformers`
download into `HF_HOME` on first use, and cache there for subsequent
calls within the same job. This is the default pattern for laptop dev
and for cluster runs where you haven't pre-downloaded or baked weights.

WATCH OUT on cluster:
- `HF_HOME` MUST point at Mimer project storage (or /tmp for ephemeral
  jobs), NEVER `~/.cache/huggingface/` — that's on Cephyr and blows
  the 60,000-file quota.
- Every new compute node is a cold cache unless you point everyone at
  the same Mimer path.
- Gated models need HF_TOKEN.
"""
from __future__ import annotations

import os
import warnings
from functools import lru_cache
from pathlib import Path
from typing import Any

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, PreTrainedModel, PreTrainedTokenizer

from . import config


def _resolve_source() -> str:
    model_id = config.hf_model_id()
    if not model_id:
        raise RuntimeError(
            "HF_MODEL is not set. Set it to a HuggingFace repo id in .env, "
            "e.g. HF_MODEL=google/gemma-2-2b-it"
        )
    return model_id


def _check_hf_home() -> None:
    """Emit a warning if HF_HOME looks dangerous on cluster."""
    hf_home = os.environ.get("HF_HOME", "")
    if not hf_home:
        warnings.warn(
            "HF_HOME is not set. Default ~/.cache/huggingface/ is fine on "
            "laptop but lethal on Cephyr (60k file quota). Set HF_HOME in "
            ".env and/or the sbatch before running on Alvis."
        )
    elif hf_home.startswith(str(Path.home())) or hf_home.startswith("/cephyr/"):
        warnings.warn(
            f"HF_HOME={hf_home} is under Cephyr/home. On Alvis this will "
            "hit the 60k-file quota quickly. Prefer /mimer/... or /tmp/..."
        )


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
    _check_hf_home()
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
    if text.startswith(prompt):
        text = text[len(prompt):].lstrip()
    return {
        "text":   text,
        "model":  _resolve_source(),
        "device": dev,
        "usage":  {"input_tokens":  int(inputs["input_ids"].numel()),
                   "output_tokens": int(out_ids.numel() - inputs["input_ids"].numel())},
    }
