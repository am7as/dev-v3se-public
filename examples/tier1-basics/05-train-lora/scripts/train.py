"""Run the LoRA finetune. Writes an adapter to $RESULTS_DIR/adapters/<ts>/."""
from __future__ import annotations

import json
import sys

from train_lora.train import run


def main() -> int:
    summary = run()
    print(json.dumps(summary, indent=2))
    print(f"\nAdapter saved to: {summary['adapter_dir']}")
    print("To use it:")
    print(f"  pixi run infer --adapter-dir '{summary['adapter_dir']}' --prompt 'Your prompt'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
