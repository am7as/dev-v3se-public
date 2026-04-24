"""Smoke tests: verify UNIQUE behavior of 14-git-model-bundle.

This example bakes a git-cloned model into a SIF/Docker image. The Python
code side is a thin HF loader with two resolution paths:

  1. HF_MODEL_SNAPSHOT (a local dir, e.g. /opt/model baked into the bundle)
  2. HF_MODEL (falls back to HF Hub for dev / smoke on laptop)

Tests exercise the snapshot-vs-hub resolver, the /models mount contract,
and bundle.def's baked-in path convention (MODEL_DIR=/opt/model).
"""
from __future__ import annotations

from pathlib import Path

from infer_git_model import config, model


# ---------- directory contract ----------

def test_models_dir_default_is_slash_models(monkeypatch):
    """/models is the canonical container mount for bundled models —
    docker-compose binds ${MODELS_HOST}:/models, sbatch binds $MODELS_DIR:/models.
    Changing this default silently breaks every bundle."""
    monkeypatch.delenv("MODELS_DIR", raising=False)
    assert str(config.models_dir()).replace("\\", "/") == "/models"


def test_models_dir_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("MODELS_DIR", str(tmp_path))
    assert config.models_dir() == tmp_path


def test_data_and_results_defaults(monkeypatch):
    monkeypatch.delenv("DATA_DIR", raising=False)
    monkeypatch.delenv("RESULTS_DIR", raising=False)
    assert str(config.data_dir()).replace("\\", "/") == "/data"
    assert str(config.results_dir()).replace("\\", "/") == "/results"


# ---------- HF model resolution ----------

def test_hf_model_default():
    """Default HF fallback when the bundle is NOT providing weights."""
    assert config.hf_model_id() == "google/gemma-2-2b-it"


def test_hf_model_id_env_override(monkeypatch):
    monkeypatch.setenv("HF_MODEL", "my-org/my-model")
    assert config.hf_model_id() == "my-org/my-model"


def test_snapshot_none_when_unset(monkeypatch):
    monkeypatch.delenv("HF_MODEL_SNAPSHOT", raising=False)
    assert config.hf_model_snapshot() is None


def test_snapshot_returns_path_when_set(monkeypatch):
    """HF_MODEL_SNAPSHOT is how the SIF hands a baked-in /opt/model to Python.
    Empty string should behave like unset."""
    monkeypatch.setenv("HF_MODEL_SNAPSHOT", "/opt/model")
    assert config.hf_model_snapshot() == "/opt/model"

    monkeypatch.setenv("HF_MODEL_SNAPSHOT", "")
    assert config.hf_model_snapshot() is None


def test_resolve_source_prefers_snapshot_over_hub(monkeypatch):
    """model._resolve_source() encodes the whole point of the bundle:
    if a local snapshot is present, use it, do NOT fall through to HF Hub."""
    monkeypatch.setenv("HF_MODEL", "should-not-be-used/model")
    monkeypatch.setenv("HF_MODEL_SNAPSHOT", "/opt/model")
    assert model._resolve_source() == "/opt/model"


def test_resolve_source_falls_back_to_hub_when_no_snapshot(monkeypatch):
    """Dev/laptop smoke: no bundle, so fall back to Hub."""
    monkeypatch.delenv("HF_MODEL_SNAPSHOT", raising=False)
    monkeypatch.setenv("HF_MODEL", "some-org/some-model")
    assert model._resolve_source() == "some-org/some-model"


# ---------- inference-config knobs ----------

def test_device_and_dtype_defaults(monkeypatch):
    monkeypatch.delenv("HF_DEVICE", raising=False)
    monkeypatch.delenv("HF_DTYPE", raising=False)
    assert config.device() == "auto"
    assert config.dtype() == "auto"


def test_max_new_tokens_default_and_override(monkeypatch):
    monkeypatch.delenv("HF_MAX_NEW_TOKENS", raising=False)
    assert config.max_new_tokens() == 200
    monkeypatch.setenv("HF_MAX_NEW_TOKENS", "32")
    assert config.max_new_tokens() == 32
