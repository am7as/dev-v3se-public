from __future__ import annotations

import json
import sys

from data_multi import config, sources


def main() -> int:
    json.dump({
        "template":       "data-multi",
        "current_source": config.source(),
        "available":      sources.available(),
        "data_dir":       str(config.data_dir()),
        "results_dir":    str(config.results_dir()),
    }, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
