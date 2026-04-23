"""Dump config as JSON without loading the model."""
from __future__ import annotations

import json
import sys

from hf_shared_hub import config


def main() -> int:
    json.dump({
        "template":             "infer-hf",
        "data_dir":             str(config.data_dir()),
        "results_dir":          str(config.results_dir()),
        "hf_model_id":          config.hf_model_id(),
        "hf_model_snapshot":    config.hf_model_snapshot(),
        "device":               config.device(),
        "dtype":                config.dtype(),
        "max_new_tokens":       config.max_new_tokens(),
    }, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
