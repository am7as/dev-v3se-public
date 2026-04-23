"""Smoke tests — import everything, exercise happy-path entrypoints."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from foundation import config, devices, manifest


def test_paths_resolve():
    assert config.data_dir()
    assert config.results_dir()
    assert config.models_dir()
    assert config.workspace_dir()


def test_device_collect_has_expected_sections():
    d = devices.collect()
    assert set(d.keys()) == {"cpu", "gpu", "runtime", "env"}
    assert d["cpu"]["logical_cores"] >= 1
    assert isinstance(d["gpu"], list)
    assert d["runtime"]["python_version"]


def test_manifest_builds_without_errors():
    m = manifest.build_manifest()
    assert m["template"] == "foundation"
    assert "timestamp" in m


def test_manifest_write_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path))
    out = manifest.write_manifest()
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["template"] == "foundation"
    assert data["paths"]["results_dir"] == str(tmp_path)
