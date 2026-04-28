from __future__ import annotations

import json
import sys

from train_infer import config


def main() -> int:
    json.dump({
        "template":      "train-infer",
        "model":         config.model_id(),
        "dataset":       config.dataset_id() or "(built-in sample)",
        "lora_r":        config.lora_r(),
        "num_epochs":    config.num_epochs(),
        "results_dir":   str(config.results_dir()),
    }, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
