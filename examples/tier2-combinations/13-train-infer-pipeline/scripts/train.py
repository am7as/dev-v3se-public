from __future__ import annotations

import json
import sys

from train_infer.train import run


def main() -> int:
    s = run()
    print(json.dumps(s, indent=2))
    print(f"\nAdapter: {s['adapter_dir']}")
    print("Next steps:")
    print(f"  pixi run bundle --adapter-dir '{s['adapter_dir']}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
