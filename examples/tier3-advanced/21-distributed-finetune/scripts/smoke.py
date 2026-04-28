from __future__ import annotations

import json
import sys

from dist_ft import config


def main() -> int:
    info: dict = {"template": "dist-ft",
                  "model":    config.model_id(),
                  "dataset":  config.dataset_id()}
    for name in ["torch", "transformers", "accelerate", "deepspeed", "trl",
                 "datasets", "wandb", "evaluate"]:
        try:
            m = __import__(name)
            info[name] = getattr(m, "__version__", "?")
        except ImportError as e:
            info[f"{name}_error"] = str(e)
    try:
        import torch
        info["cuda_available"] = torch.cuda.is_available()
        info["gpu_count"]      = torch.cuda.device_count()
    except ImportError:
        pass
    print(json.dumps(info, indent=2))
    out = config.ensure_results_dir() / "smoke.json"
    out.write_text(json.dumps(info, indent=2))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
