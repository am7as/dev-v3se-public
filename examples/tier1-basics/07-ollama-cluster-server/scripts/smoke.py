"""Smoke: print env info + confirm the OpenAI SDK imports (no API call)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from ollama_cluster import config


def main() -> int:
    info = {
        "template":        "infer-api",
        "python":          sys.version.split()[0],
        "data_dir":        str(config.data_dir()),
        "results_dir":     str(config.results_dir()),
        "openai_model":    config.openai_model(),
        "openai_base_url": config.openai_base_url() or "(default openai.com)",
        "api_key_present": bool(os.environ.get("OPENAI_API_KEY")),
    }

    # Confirm SDK loads (no network call).
    try:
        import openai  # noqa: F401
        info["openai_sdk"] = "ok"
    except ImportError as e:
        info["openai_sdk"] = f"missing: {e}"

    print(json.dumps(info, indent=2))
    out = config.ensure_results_dir() / "smoke.json"
    out.write_text(json.dumps(info, indent=2))
    print(f"\nwrote {out}")
    return 0 if info["openai_sdk"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
