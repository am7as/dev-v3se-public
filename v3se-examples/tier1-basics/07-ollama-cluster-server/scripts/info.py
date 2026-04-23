"""Dump env info as JSON to stdout. No side effects. No API call."""
from __future__ import annotations

import json
import os
import sys

from ollama_cluster import config


def main() -> int:
    json.dump({
        "template":        "infer-api",
        "data_dir":        str(config.data_dir()),
        "results_dir":     str(config.results_dir()),
        "openai_model":    config.openai_model(),
        "openai_base_url": config.openai_base_url() or "(default)",
        "api_key_present": bool(os.environ.get("OPENAI_API_KEY")),
    }, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
