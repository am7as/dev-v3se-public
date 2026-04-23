from __future__ import annotations

import json
import sys

from train_lora import config


def main() -> int:
    json.dump({
        "template":       "train-lora",
        "model":          config.model_id(),
        "model_snapshot": config.model_snapshot(),
        "dataset":        config.dataset_id() or "(built-in sample)",
        "lora_r":         config.lora_r(),
        "lora_alpha":     config.lora_alpha(),
        "lora_dropout":   config.lora_dropout(),
        "num_epochs":     config.num_epochs(),
        "batch_size":     config.batch_size(),
        "learning_rate":  config.learning_rate(),
        "results_dir":    str(config.results_dir()),
    }, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
