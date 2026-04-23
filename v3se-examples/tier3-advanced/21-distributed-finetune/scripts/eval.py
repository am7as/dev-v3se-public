"""Quick eval: generate from a set of held-out prompts, compute
perplexity, save a report.

Handles three checkpoint shapes transparently:
  1. Standard HF tree (config.json + model.safetensors or sharded index) —
     loaded directly via `AutoModelForCausalLM.from_pretrained`.
  2. ZeRO-3 sharded checkpoints written by DeepSpeed (pytorch_model/ dir
     containing `mp_rank_*.pt` shards) — consolidated to fp32 first via
     `zero_to_fp32.py`, then loaded.
  3. FSDP sharded state dicts written by `accelerate` (a directory of
     `*.safetensors` shards without a merged `model.safetensors.index.json`)
     — merged via `accelerate merge-weights` first.

Pick `--ckpt-dir` as the directory holding the raw training output; the
script detects the shape and consolidates into a sibling `<ckpt>.consolidated/`
dir when needed, then loads from there.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from dist_ft import config


HELD_OUT = [
    "Q: What is the capital of France?\nA:",
    "Q: Explain gradient descent in one sentence.\nA:",
    "Q: Who wrote Hamlet?\nA:",
]


def _is_deepspeed_zero(ckpt_dir: Path) -> bool:
    """ZeRO-3 layout: `global_step*/` or `pytorch_model/` with `mp_rank_*.pt`."""
    if (ckpt_dir / "zero_to_fp32.py").exists():
        return True
    if any(ckpt_dir.glob("global_step*/mp_rank_*_model_states.pt")):
        return True
    return False


def _is_fsdp_sharded(ckpt_dir: Path) -> bool:
    """FSDP accelerate layout: many *.safetensors shards without a HF index."""
    shards = list(ckpt_dir.glob("*.safetensors"))
    has_index = (ckpt_dir / "model.safetensors.index.json").exists() or \
                (ckpt_dir / "pytorch_model.bin.index.json").exists()
    has_single = (ckpt_dir / "model.safetensors").exists() or \
                 (ckpt_dir / "pytorch_model.bin").exists()
    return len(shards) > 0 and not has_index and not has_single


def _consolidate(ckpt_dir: Path) -> Path:
    """Consolidate sharded checkpoints into a loadable HF-format dir.

    Returns the path to the consolidated dir (either the original if no
    consolidation was needed, or a sibling `<ckpt>.consolidated/`).
    """
    out_dir = ckpt_dir.with_name(ckpt_dir.name + ".consolidated")

    if _is_deepspeed_zero(ckpt_dir):
        if out_dir.exists():
            print(f"[eval] using cached consolidated dir: {out_dir}")
            return out_dir
        print(f"[eval] DeepSpeed ZeRO-3 layout detected — consolidating to {out_dir}")
        out_dir.mkdir(parents=True, exist_ok=True)
        script = ckpt_dir / "zero_to_fp32.py"
        if not script.exists():
            raise RuntimeError(
                f"Expected {script} (ships with DeepSpeed training output). "
                "Re-run training with the DeepSpeed wrapper, or point --ckpt-dir "
                "at a checkpoint directory that contains it."
            )
        subprocess.check_call([
            sys.executable, str(script), str(ckpt_dir), str(out_dir / "pytorch_model.bin"),
        ])
        # Copy over config + tokenizer so from_pretrained() can find them.
        for f in ckpt_dir.iterdir():
            if f.suffix in {".json", ".model"} or f.name.startswith("tokenizer"):
                shutil.copy2(f, out_dir / f.name)
        return out_dir

    if _is_fsdp_sharded(ckpt_dir):
        if out_dir.exists():
            print(f"[eval] using cached consolidated dir: {out_dir}")
            return out_dir
        print(f"[eval] FSDP sharded layout detected — consolidating to {out_dir}")
        out_dir.mkdir(parents=True, exist_ok=True)
        # `accelerate merge-weights` consolidates into a single safetensors file.
        subprocess.check_call([
            "accelerate", "merge-weights", str(ckpt_dir), str(out_dir),
        ])
        for f in ckpt_dir.iterdir():
            if f.suffix in {".json", ".model"} or f.name.startswith("tokenizer"):
                shutil.copy2(f, out_dir / f.name)
        return out_dir

    # Already a standard HF tree — load directly.
    return ckpt_dir


def _perplexity(model, tokenizer, text: str, device: str) -> float:
    ids = tokenizer(text, return_tensors="pt").input_ids.to(device)
    with torch.no_grad():
        loss = model(ids, labels=ids).loss
    return float(math.exp(loss.item()))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt-dir", type=Path, required=True)
    args = ap.parse_args(argv)

    load_dir = _consolidate(args.ckpt_dir)

    tok = AutoTokenizer.from_pretrained(str(load_dir))
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(str(load_dir),
                                                 torch_dtype=torch.bfloat16)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device).eval()

    results = []
    for prompt in HELD_OUT:
        ids = tok(prompt, return_tensors="pt").to(device)
        out = model.generate(**ids, max_new_tokens=80, do_sample=False)
        text = tok.decode(out[0], skip_special_tokens=True)
        ppl = _perplexity(model, tok, prompt, device)
        results.append({"prompt": prompt, "generation": text, "perplexity": ppl})

    report = {"ckpt": str(args.ckpt_dir),
              "loaded_from": str(load_dir),
              "mean_ppl": sum(r["perplexity"] for r in results) / len(results),
              "samples": results}
    out = config.ensure_results_dir() / "eval_report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps({"ckpt": str(args.ckpt_dir), "mean_ppl": report["mean_ppl"],
                      "out": str(out)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
