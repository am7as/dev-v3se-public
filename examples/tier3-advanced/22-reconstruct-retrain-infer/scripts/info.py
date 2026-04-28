from __future__ import annotations

import json
import sys

from reco import config


def main() -> int:
    json.dump({
        "template":        "reco",
        "base_model":      config.model_id(),
        "dataset":         config.dataset_id(),
        "num_labels":      config.num_labels(),
        "num_epochs":      config.num_epochs(),
        "surgery_config":  config.surgery_config_path(),
        "results_dir":     str(config.results_dir()),
    }, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
