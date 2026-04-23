"""Call the configured OpenAI-compatible API with a prompt; save the response.

Usage:
    pixi run infer --prompt "What is 2+2?"
    pixi run infer --prompt-file prompt.txt
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

from infer_api import config
from infer_api.providers import predict


def _utc_stamp() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Call the configured API with a prompt.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--prompt", help="Prompt text as a CLI argument.")
    g.add_argument("--prompt-file", type=Path, help="Read prompt from a file.")
    ap.add_argument("--model", default=None, help="Override OPENAI_MODEL.")
    ap.add_argument("--temperature", type=float, default=0.0)
    args = ap.parse_args(argv)

    prompt = args.prompt if args.prompt else args.prompt_file.read_text(encoding="utf-8")

    response = predict(prompt, model=args.model, temperature=args.temperature)

    out_dir = config.ensure_results_dir() / "responses"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{_utc_stamp()}.json"
    record = {
        "prompt":   prompt,
        "model":    response["model"],
        "text":     response["text"],
        "usage":    response["usage"],
    }
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")

    print(response["text"])
    print(f"\n--- {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
