from __future__ import annotations

import json
import sys

from dist_ft import config


def main() -> int:
    json.dump({
        "template":          "dist-ft",
        "model":             config.model_id(),
        "dataset":           config.dataset_id(),
        "num_epochs":        config.num_epochs(),
        "per_device_batch":  config.per_device_batch(),
        "grad_accum":        config.grad_accum(),
        "max_seq_len":       config.max_seq_len(),
        "results_dir":       str(config.results_dir()),
    }, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
