"""Write a manifest JSON to RESULTS_DIR."""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any

from . import config, devices

__all__ = ["build_manifest", "write_manifest"]


def _utc_stamp() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_manifest() -> dict[str, Any]:
    return {
        "template":   "__PROJECT_SLUG__",
        "version":    "0.1.0",
        "timestamp":  _utc_stamp(),
        "paths": {
            "data_dir":      str(config.data_dir()),
            "results_dir":   str(config.results_dir()),
            "models_dir":    str(config.models_dir()),
            "workspace_dir": str(config.workspace_dir()),
        },
        **devices.collect(),
    }


def write_manifest(manifest: dict[str, Any] | None = None) -> Path:
    manifest = manifest or build_manifest()
    out_dir = config.ensure_results_dir()
    out_path = out_dir / f"manifest-{manifest['timestamp']}.json"
    out_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return out_path
