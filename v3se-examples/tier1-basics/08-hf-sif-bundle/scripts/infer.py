"""Generate text from the configured HF model.

    pixi run infer --prompt "Once upon a time"
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

from hf_sif_bundle import config
from hf_sif_bundle.model import generate


def _ts() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--prompt")
    g.add_argument("--prompt-file", type=Path)
    ap.add_argument("--max-new-tokens", type=int, default=None)
    args = ap.parse_args(argv)

    prompt = args.prompt or args.prompt_file.read_text(encoding="utf-8")

    r = generate(prompt, max_new_tokens=args.max_new_tokens)

    out_dir = config.ensure_results_dir() / "responses"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{_ts()}.json"
    out.write_text(json.dumps({"prompt": prompt, **r}, indent=2, ensure_ascii=False),
                   encoding="utf-8")

    print(r["text"])
    print(f"\n--- {out}")
    print(f"model={r['model']}  device={r['device']}  tokens={r['usage']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
