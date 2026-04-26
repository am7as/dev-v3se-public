"""Run inference on any configured provider.

    Cloud APIs:
        pixi run infer --provider openai     --prompt "hi"
        pixi run infer --provider gemini     --prompt "hi"
    CLI subscription:
        pixi run infer --provider claude_cli --prompt "hi"
    Local servers (OpenAI-compatible HTTP):
        pixi run infer --provider lmstudio   --prompt "hi"
        pixi run infer --provider ollama     --prompt "hi"
    Cluster server:
        pixi run infer --provider vllm       --prompt "hi"
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

from infer_multi import config, router, providers


def _ts() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default=None, choices=[*providers.available(), None])
    ap.add_argument("--model", default=None)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--prompt")
    g.add_argument("--prompt-file", type=Path)
    args = ap.parse_args(argv)

    prompt = args.prompt or args.prompt_file.read_text(encoding="utf-8")
    r = router.predict(prompt, provider=args.provider, model=args.model)

    out_dir = config.ensure_results_dir() / "responses"
    out_dir.mkdir(parents=True, exist_ok=True)
    provider_name = args.provider or config.default_provider()
    out = out_dir / f"{provider_name}__{_ts()}.json"
    out.write_text(json.dumps({
        "provider": provider_name,
        "model":    r["model"],
        "prompt":   prompt,
        "text":     r["text"],
        "usage":    r["usage"],
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    print(r["text"])
    print(f"\n--- {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
