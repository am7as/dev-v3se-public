from __future__ import annotations

import json
import sys

from data_cephyr import config


def main() -> int:
    json.dump({
        "template":    "data-cephyr",
        "data_dir":    str(config.data_dir()),
        "results_dir": str(config.results_dir()),
        "dataset":     config.dataset(),
    }, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
