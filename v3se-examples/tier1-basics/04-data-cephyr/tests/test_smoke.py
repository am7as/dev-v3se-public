import json
from pathlib import Path

import pandas as pd
import pytest

from data_cephyr import config, processing


def test_config_reads_env(monkeypatch):
    monkeypatch.setenv("DATASET", "private")
    assert config.dataset() == "private"


def test_summarize_dataframe_numeric():
    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    s = processing.summarize_dataframe(df)
    assert s["rows"] == 3
    assert s["cols"] == 2
    assert s["numeric_stats"]["a"]["min"] == 1.0
    assert s["numeric_stats"]["a"]["max"] == 3.0
    assert "b" not in s["numeric_stats"]


def test_process_writes_summary(tmp_path):
    # Write a tiny CSV
    d = tmp_path / "data"
    d.mkdir()
    pd.DataFrame({"n": [10, 20, 30]}).to_csv(d / "a.csv", index=False)
    pd.DataFrame({"n": [100]}).to_csv(d / "b.csv", index=False)

    out = tmp_path / "out.json"
    result = processing.process(d, out)

    assert out.exists()
    assert result["file_count"] == 2
    assert result["total_rows"] == 4


def test_process_raises_on_empty(tmp_path):
    with pytest.raises(FileNotFoundError, match="No CSVs"):
        processing.process(tmp_path, tmp_path / "out.json")
