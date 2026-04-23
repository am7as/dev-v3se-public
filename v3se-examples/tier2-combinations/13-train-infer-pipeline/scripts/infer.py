"""Generate text from base model + LoRA adapter.

Usable in two ways:
    (A) Inside the dev/app SIF, with an explicit --adapter-dir
    (B) Inside a BUNDLED SIF — the adapter is at /opt/adapter and the
        bundler sets BUNDLED_ADAPTER_DIR; just pass --prompt.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

from train_infer import config


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter-dir", type=Path, default=None)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--max-new-tokens", type=int, default=80)
    args = ap.parse_args(argv)

    adapter_dir = args.adapter_dir or Path(os.environ.get("BUNDLED_ADAPTER_DIR", ""))
    if not adapter_dir or not adapter_dir.exists():
        print("No adapter dir found. Pass --adapter-dir or run from a bundled SIF.",
              file=sys.stderr)
        return 1

    base = config.model_snapshot() or config.model_id()
    token = os.environ.get("HF_TOKEN") or None

    tok = AutoTokenizer.from_pretrained(str(adapter_dir), token=token)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    model = AutoModelForCausalLM.from_pretrained(base, token=token)
    model = PeftModel.from_pretrained(model, str(adapter_dir))
    model.eval()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)

    inputs = tok(args.prompt, return_tensors="pt").to(device)
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=args.max_new_tokens, do_sample=False)
    print(tok.decode(out[0], skip_special_tokens=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
