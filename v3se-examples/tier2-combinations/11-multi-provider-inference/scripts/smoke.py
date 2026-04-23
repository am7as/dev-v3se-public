"""Smoke: confirm providers import + report which are usable."""
from __future__ import annotations

import json
import os
import shutil
import sys

from infer_multi import config, providers


def main() -> int:
    info = {
        "template": "infer-multi",
        "default_provider": config.default_provider(),
        "available": providers.available(),
        "status": {
            "openai":     "ok" if os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_BASE_URL") else "missing OPENAI_API_KEY/BASE_URL",
            "claude_cli": "ok" if shutil.which(os.environ.get("CLAUDE_CLI_PATH") or "claude") else "missing claude binary",
            "vllm":       "ok" if os.environ.get("VLLM_PORT") or os.path.exists(os.environ.get("VLLM_PORT_FILE", "/results/vllm-port.txt")) else "no VLLM_PORT or port file",
        },
    }
    print(json.dumps(info, indent=2))
    out = config.ensure_results_dir() / "smoke.json"
    out.write_text(json.dumps(info, indent=2))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
