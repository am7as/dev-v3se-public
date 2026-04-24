"""Smoke tests — no network, no large files.

The unique thing about this template is the private-data ETL pattern
on Cephyr: recursively find CSVs under DATA_DIR, summarise each one,
write a single JSON to RESULTS_DIR. These tests pin that contract.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from data_cephyr import config, processing


# --------------------------------------------------------------------------- #
# config — DATASET switch + path defaults                                     #
# --------------------------------------------------------------------------- #

def test_dataset_defaults_to_sample(monkeypatch):
    """Blank-template default: the canned 'sample' dataset, so fresh
    clones produce output without the user touching anything."""
    monkeypatch.delenv("DATASET", raising=False)
    assert config.dataset() == "sample"


def test_config_reads_env(monkeypatch):
    monkeypatch.setenv("DATASET", "private")
    assert config.dataset() == "private"


def test_data_dir_respects_env_override(monkeypatch, tmp_path):
    """On Alvis the `data-cephyr` sbatch binds Cephyr-user data onto
    /data via DATA_DIR — must honour the override."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert config.data_dir() == tmp_path


def test_ensure_results_dir_creates_missing_tree(monkeypatch, tmp_path):
    target = tmp_path / "new" / "results"
    monkeypatch.setenv("RESULTS_DIR", str(target))
    out = config.ensure_results_dir()
    assert out == target
    assert target.is_dir()


# --------------------------------------------------------------------------- #
# processing — the actual ETL                                                 #
# --------------------------------------------------------------------------- #

def test_summarize_dataframe_keeps_only_numeric_stats():
    """Numeric-stats dict must exclude non-numeric columns — otherwise the
    JSON output blows up on string columns."""
    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    s = processing.summarize_dataframe(df)
    assert s["rows"] == 3
    assert s["cols"] == 2
    assert s["columns"] == ["a", "b"]
    assert s["numeric_stats"]["a"]["min"] == 1.0
    assert s["numeric_stats"]["a"]["max"] == 3.0
    assert s["numeric_stats"]["a"]["mean"] == 2.0
    assert "b" not in s["numeric_stats"]
    # null_counts covers every column, numeric or not.
    assert s["null_counts"] == {"a": 0, "b": 0}


def test_list_csvs_walks_recursively(tmp_path):
    """Cephyr dataset layouts are often nested (year/month/file.csv). The
    walker must rglob, not just glob the top level."""
    (tmp_path / "2024" / "01").mkdir(parents=True)
    (tmp_path / "2024" / "02").mkdir()
    (tmp_path / "2024" / "01" / "a.csv").write_text("x\n1\n")
    (tmp_path / "2024" / "02" / "b.csv").write_text("x\n2\n")
    (tmp_path / "not-a-csv.txt").write_text("ignore me")

    found = processing.list_csvs(tmp_path)
    assert len(found) == 2
    assert all(p.suffix == ".csv" for p in found)
    # Sorted output — stable for reproducible runs.
    assert found == sorted(found)


def test_process_writes_summary(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    pd.DataFrame({"n": [10, 20, 30]}).to_csv(d / "a.csv", index=False)
    pd.DataFrame({"n": [100]}).to_csv(d / "b.csv", index=False)

    out = tmp_path / "out.json"
    result = processing.process(d, out)

    assert out.exists()
    assert result["file_count"] == 2
    assert result["total_rows"] == 4
    # The JSON on disk must match what the call returned.
    on_disk = json.loads(out.read_text())
    assert on_disk["total_rows"] == 4
    assert set(on_disk["files"].keys()) == {"a.csv", "b.csv"}


def test_process_raises_on_empty(tmp_path):
    """Empty DATA_DIR → FileNotFoundError with a pointer to DATA_DIR. This
    is how users on Alvis realise the Cephyr bind-mount didn't land."""
    with pytest.raises(FileNotFoundError, match="DATA_DIR"):
        processing.process(tmp_path, tmp_path / "out.json")


def test_process_creates_output_parents(tmp_path):
    """`out_path` may live under a fresh RESULTS_DIR — process() must
    mkdir -p the parent on the way out."""
    d = tmp_path / "data"
    d.mkdir()
    pd.DataFrame({"n": [1]}).to_csv(d / "a.csv", index=False)

    out = tmp_path / "nested" / "deep" / "out.json"
    processing.process(d, out)
    assert out.exists()
