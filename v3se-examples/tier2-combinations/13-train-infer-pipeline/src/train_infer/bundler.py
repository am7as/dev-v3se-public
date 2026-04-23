"""Bundle a trained adapter + base-model reference + inference code into a SIF.

Strategy:
    1. Load the .def.tpl file.
    2. Substitute ADAPTER_SRC with the actual adapter directory.
    3. Substitute BASE_MODEL with the base model id.
    4. `apptainer build` the materialized def.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


def build(adapter_dir: Path, base_model: str, out_sif: Path,
          tpl_path: Path | None = None) -> Path:
    tpl_path = tpl_path or (Path(__file__).resolve().parents[2] /
                             "apptainer" / "bundle.def.tpl")
    if not tpl_path.exists():
        raise FileNotFoundError(f"Bundle template not found: {tpl_path}")
    if not adapter_dir.exists():
        raise FileNotFoundError(f"Adapter dir not found: {adapter_dir}")

    tpl = tpl_path.read_text()
    def_text = (
        tpl
        .replace("ADAPTER_SRC", str(adapter_dir))
        .replace("BASE_MODEL", base_model)
    )

    out_def = out_sif.with_suffix(".def")
    out_def.parent.mkdir(parents=True, exist_ok=True)
    out_def.write_text(def_text)

    print(f"Building {out_sif} from {out_def} …")
    subprocess.run(["apptainer", "build", "-F", str(out_sif), str(out_def)],
                   check=True)

    # Record what's inside
    manifest = {
        "sif":          str(out_sif),
        "def":          str(out_def),
        "adapter_dir":  str(adapter_dir),
        "base_model":   base_model,
    }
    out_sif.with_suffix(".json").write_text(json.dumps(manifest, indent=2))
    return out_sif
