from __future__ import annotations

import json
import sys

from infer_multi import config, providers


def main() -> int:
    json.dump({
        "template":         "infer-multi",
        "default_provider": config.default_provider(),
        "available":        providers.available(),
        "results_dir":      str(config.results_dir()),
    }, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
