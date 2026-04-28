from __future__ import annotations

import json
import sys

from train_infer import config


def main() -> int:
    info: dict = {"template": "train-infer",
                  "model":    config.model_id(),
                  "results_dir": str(config.results_dir())}
    for name in ["torch", "transformers", "peft", "datasets", "trl", "accelerate",
                 "wandb", "mlflow"]:
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
