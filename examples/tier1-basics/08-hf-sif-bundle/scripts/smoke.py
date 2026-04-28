"""Smoke: check torch + transformers import and GPU visibility, without
actually loading a model (downloads can take minutes on first run)."""
from __future__ import annotations

import json
import sys

from hf_sif_bundle import config


def main() -> int:
    info = {"template": "infer-hf"}
    try:
        import torch
        info["torch"] = torch.__version__
        info["cuda_available"] = torch.cuda.is_available()
        info["cuda_device_count"] = torch.cuda.device_count()
        info["cuda_devices"] = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
    except ImportError as e:
        info["torch_error"] = str(e)
        print(json.dumps(info, indent=2))
        return 1

    try:
        import transformers
        info["transformers"] = transformers.__version__
    except ImportError as e:
        info["transformers_error"] = str(e)

    info["hf_model_id"] = config.hf_model_id()
    info["hf_model_snapshot"] = config.hf_model_snapshot() or "(none — will download)"
    info["device_setting"] = config.device()
    info["results_dir"] = str(config.results_dir())

    print(json.dumps(info, indent=2))
    out = config.ensure_results_dir() / "smoke.json"
    out.write_text(json.dumps(info, indent=2))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
