"""Generic summary over any of the sources."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def summarize_csvs(root: Path) -> dict[str, Any]:
    csvs = sorted(p for p in root.rglob("*.csv") if p.is_file())
    if not csvs:
        return {"file_count": 0, "note": f"No CSVs under {root}"}
    per_file = {}
    total_rows = 0
    for csv in csvs:
        df = pd.read_csv(csv)
        rel = str(csv.relative_to(root))
        per_file[rel] = {"rows": int(df.shape[0]), "cols": int(df.shape[1])}
        total_rows += int(df.shape[0])
    return {
        "root": str(root),
        "file_count": len(csvs),
        "total_rows": total_rows,
        "files": per_file,
    }


def summarize_hf_dataset(ds) -> dict[str, Any]:
    return {
        "rows":     int(len(ds)),
        "columns":  list(ds.column_names),
        "example":  ds[0] if len(ds) else None,
    }


def write_summary(summary: dict[str, Any], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    return out_path
