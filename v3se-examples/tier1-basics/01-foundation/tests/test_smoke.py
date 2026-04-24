"""Smoke tests — import everything, exercise happy-path entrypoints.

These tests are deliberately hermetic: no network, no GPU, no subprocess
beyond what `devices.collect()` runs on its own. Each test should finish
in well under one second.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from foundation import config, devices, manifest


# --------------------------------------------------------------------------- #
# config — every path getter must honour its env-var override                 #
# --------------------------------------------------------------------------- #

def test_paths_resolve_to_container_defaults(monkeypatch):
    """With no env vars set, paths fall back to the fixed /data, /results,
    /models, /workspace mounts — the V3SE container contract."""
    for var in ("DATA_DIR", "RESULTS_DIR", "MODELS_DIR", "WORKSPACE_DIR"):
        monkeypatch.delenv(var, raising=False)
    assert config.data_dir()      == Path("/data")
    assert config.results_dir()   == Path("/results")
    assert config.models_dir()    == Path("/models")
    assert config.workspace_dir() == Path("/workspace")


def test_data_dir_respects_env_override(monkeypatch, tmp_path):
    """DATA_DIR env var must take precedence over the /data default — this
    is what lets the sample bind-mount a sibling folder during a laptop run."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert config.data_dir() == tmp_path


def test_ensure_results_dir_creates_missing_tree(monkeypatch, tmp_path):
    """ensure_results_dir() must mkdir -p the target, so Slurm jobs can't
    fail on a fresh $RESULTS_DIR."""
    target = tmp_path / "nested" / "results"
    monkeypatch.setenv("RESULTS_DIR", str(target))
    out = config.ensure_results_dir()
    assert out == target
    assert target.is_dir()


# --------------------------------------------------------------------------- #
# devices — inventory of the host                                             #
# --------------------------------------------------------------------------- #

def test_device_collect_has_expected_sections():
    d = devices.collect()
    assert set(d.keys()) == {"cpu", "gpu", "runtime", "env"}
    assert d["cpu"]["logical_cores"] >= 1
    assert isinstance(d["gpu"], list)
    assert d["runtime"]["python_version"]


def test_device_env_reports_contract_keys(monkeypatch):
    """`env` section must always include the V3SE path contract keys —
    that's how `manifest.json` shows which overrides were in effect."""
    monkeypatch.setenv("DATA_DIR", "/tmp/probe-data")
    d = devices.collect()
    assert "DATA_DIR" in d["env"]
    assert "RESULTS_DIR" in d["env"]
    assert "HF_HOME" in d["env"]
    assert "CUDA_VISIBLE_DEVICES" in d["env"]
    assert d["env"]["DATA_DIR"] == "/tmp/probe-data"


def test_runtime_detects_slurm(monkeypatch):
    monkeypatch.setenv("SLURM_JOB_ID", "12345")
    monkeypatch.setenv("SLURMD_NODENAME", "alvis1-02")
    rt = devices.runtime_info()
    assert rt["in_slurm"] is True
    assert rt["slurm_job_id"] == "12345"
    assert rt["slurm_node"] == "alvis1-02"


# --------------------------------------------------------------------------- #
# manifest — the artefact this template actually writes                       #
# --------------------------------------------------------------------------- #

def test_manifest_identifies_this_template():
    """The manifest self-identifies as the `foundation` template — lets
    downstream wrappers tell sibling scaffolds apart."""
    m = manifest.build_manifest()
    assert m["template"] == "foundation"
    assert m["version"]
    assert "timestamp" in m
    # build_manifest() folds the whole device inventory into the top level
    assert "cpu" in m and "gpu" in m and "runtime" in m and "env" in m


def test_manifest_paths_track_config(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "d"))
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path / "r"))
    m = manifest.build_manifest()
    assert m["paths"]["data_dir"]    == str(tmp_path / "d")
    assert m["paths"]["results_dir"] == str(tmp_path / "r")


def test_manifest_write_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path))
    out = manifest.write_manifest()
    assert out.exists()
    assert out.name.startswith("manifest-") and out.suffix == ".json"
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["template"] == "foundation"
    assert data["paths"]["results_dir"] == str(tmp_path)
