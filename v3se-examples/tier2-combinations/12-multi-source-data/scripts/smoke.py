from __future__ import annotations

import json
import sys

from data_multi import config, sources


def main() -> int:
    info = {
        "template":      "data-multi",
        "current_source": config.source(),
        "available":     sources.available(),
        "data_dir":      str(config.data_dir()),
        "results_dir":   str(config.results_dir()),
    }
    print(json.dumps(info, indent=2))
    out = config.ensure_results_dir() / "smoke.json"
    out.write_text(json.dumps(info, indent=2))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
