"""Tiny ETL: read every CSV under a directory, compute summary stats.

Purpose: demonstrate the read-data / write-results flow without needing
a specific domain dataset. The real lesson is in how /data and /results
are wired, not the analytics.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def list_csvs(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.csv") if p.is_file())


def summarize_dataframe(df: pd.DataFrame) -> dict[str, Any]:
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    summary = {
        "rows": int(df.shape[0]),
        "cols": int(df.shape[1]),
        "columns": df.columns.tolist(),
        "numeric_stats": {
            col: {
                "min":  float(df[col].min()),
                "max":  float(df[col].max()),
                "mean": float(df[col].mean()),
            }
            for col in numeric_cols
        },
        "null_counts": {col: int(df[col].isna().sum()) for col in df.columns},
    }
    return summary


def process(source_dir: Path, out_path: Path) -> dict[str, Any]:
    csvs = list_csvs(source_dir)
    if not csvs:
        raise FileNotFoundError(f"No CSVs under {source_dir}. Check DATA_DIR.")

    per_file: dict[str, Any] = {}
    total_rows = 0
    for csv in csvs:
        df = pd.read_csv(csv)
        rel = str(csv.relative_to(source_dir))
        per_file[rel] = summarize_dataframe(df)
        total_rows += int(df.shape[0])

    result = {
        "source_dir": str(source_dir),
        "file_count": len(csvs),
        "total_rows": total_rows,
        "files": per_file,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2))
    return result
