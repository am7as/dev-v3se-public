"""Dump full device + env info as JSON to stdout. No side effects.

    pixi run info
"""
from __future__ import annotations

import json
import sys

from foundation import manifest as _manifest


def main() -> int:
    m = _manifest.build_manifest()
    json.dump(m, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
