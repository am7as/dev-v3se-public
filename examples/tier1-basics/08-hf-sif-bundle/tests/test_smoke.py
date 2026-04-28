"""Smoke tests for the hf-sif-bundle template.

These tests exercise behavior UNIQUE to the SIF-bundled pattern vs.
its sibling 09-hf-hub-streaming:
  - Weights are BAKED INTO the Apptainer SIF at build time. At run
    time, `model.MODEL_DIR` points at a container-internal path
    (default `/opt/model`) and `from_pretrained` is called with
    `local_files_only=True`. NO hub access ever.
  - `model._resolve_source()` raises `RuntimeError` if the baked
    directory is missing — that's the "built without weights" tripwire.
  - The module has NO `_check_hf_home` helper (HF_HOME is irrelevant
    inside a bundled SIF).

No network, no model loading, no transformers-from-pretrained calls.
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from hf_sif_bundle import config, model


# --------------------------------------------------------------------------
# config — same pattern as 09 but retained so the test file is self-contained.
# --------------------------------------------------------------------------
def test_defaults():
    assert config.data_dir()
    assert config.hf_model_id()


def test_config_reads_env(monkeypatch):
    monkeypatch.setenv("HF_MODEL", "my-org/my-model")
    assert config.hf_model_id() == "my-org/my-model"


# --------------------------------------------------------------------------
# model.MODEL_DIR — the SIF-baked path. This is 08's distinguishing feature:
# 09 has no such constant.
# --------------------------------------------------------------------------
def test_model_dir_defaults_to_sif_internal_path():
    # Default must point INSIDE the container at an absolute path —
    # never at $HOME, never at a relative path.
    assert model.MODEL_DIR == Path("/opt/model")
    assert model.MODEL_DIR.is_absolute()


def test_model_dir_overridable_via_env(monkeypatch):
    # Local-dev escape hatch: point at a pre-downloaded directory on
    # the host so the example is testable outside the SIF.
    monkeypatch.setenv("MODEL_DIR", "/tmp/fake-baked-model")
    reloaded = importlib.reload(model)
    try:
        assert reloaded.MODEL_DIR == Path("/tmp/fake-baked-model")
    finally:
        monkeypatch.delenv("MODEL_DIR", raising=False)
        importlib.reload(model)


# --------------------------------------------------------------------------
# model._resolve_source — refuses to run if the SIF lacks baked weights.
# This is the tripwire that distinguishes 08 (offline, baked) from 09
# (online, streaming).
# --------------------------------------------------------------------------
def test_resolve_source_raises_when_model_dir_missing(monkeypatch, tmp_path):
    missing = tmp_path / "definitely-not-there"
    monkeypatch.setattr(model, "MODEL_DIR", missing)
    with pytest.raises(RuntimeError, match="MODEL_DIR|build-model-sif"):
        model._resolve_source()


def test_resolve_source_returns_path_when_model_dir_exists(monkeypatch, tmp_path):
    (tmp_path / "config.json").write_text("{}")  # shape of a HF snapshot
    monkeypatch.setattr(model, "MODEL_DIR", tmp_path)
    assert model._resolve_source() == str(tmp_path)


# --------------------------------------------------------------------------
# No online-mode plumbing — the SIF variant must NOT ship the HF_HOME
# warning helper that 09 uses. If this assertion ever flips, 08 and 09
# have drifted into each other.
# --------------------------------------------------------------------------
def test_no_hf_home_check_helper():
    assert not hasattr(model, "_check_hf_home")


# --------------------------------------------------------------------------
# dtype mapping — shared mechanism, but worth a fast round-trip to make
# sure the offline loader still honors the same env knobs as the online one.
# --------------------------------------------------------------------------
def test_dtype_resolution_auto_is_preserved(monkeypatch):
    monkeypatch.setenv("HF_DTYPE", "auto")
    assert model._resolve_dtype() == "auto"
