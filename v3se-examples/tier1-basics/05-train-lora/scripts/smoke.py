"""Smoke: confirm training deps import."""
from __future__ import annotations

import json
import sys

from train_lora import config


def main() -> int:
    info: dict = {"template": "train-lora",
                  "model":    config.model_id(),
                  "results_dir": str(config.results_dir()),
                  "lora_r":   config.lora_r()}
    for name in ["torch", "transformers", "peft", "datasets", "trl", "accelerate"]:
        try:
            mod = __import__(name)
            info[name] = getattr(mod, "__version__", "?")
        except ImportError as e:
            info[f"{name}_error"] = str(e)
    try:
        import torch
        info["cuda_available"] = torch.cuda.is_available()
    except ImportError:
        pass
    print(json.dumps(info, indent=2))
    out = config.ensure_results_dir() / "smoke.json"
    out.write_text(json.dumps(info, indent=2))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
