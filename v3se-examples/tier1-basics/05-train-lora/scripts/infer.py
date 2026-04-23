"""Generate text using a LoRA adapter on top of the base model."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

from train_lora import config


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter-dir", required=True, type=Path,
                    help="Directory saved by `pixi run train`.")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--max-new-tokens", type=int, default=80)
    args = ap.parse_args(argv)

    if not args.adapter_dir.exists():
        print(f"No such adapter dir: {args.adapter_dir}", file=sys.stderr)
        return 1

    base = config.model_snapshot() or config.model_id()
    token = os.environ.get("HF_TOKEN") or None

    tokenizer = AutoTokenizer.from_pretrained(str(args.adapter_dir), token=token)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(base, token=token)
    model = PeftModel.from_pretrained(model, str(args.adapter_dir))
    model.eval()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)
    inputs = tokenizer(args.prompt, return_tensors="pt").to(device)
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=args.max_new_tokens,
                             do_sample=False)
    text = tokenizer.decode(out[0], skip_special_tokens=True)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
