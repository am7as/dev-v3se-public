"""Smoke tests for the hf-hub-streaming template.

These tests exercise behavior UNIQUE to the Hub-streaming pattern vs.
its sibling 08-hf-sif-bundle:
  - Weights are downloaded from the HuggingFace Hub on first call and
    cached in `HF_HOME`. There is NO baked-in `MODEL_DIR` constant.
  - `model._check_hf_home()` emits warnings when the cache location
    looks dangerous on Alvis (unset → `~/.cache/`, or under `$HOME`,
    or under `/cephyr/`) — Cephyr has a 60k-file quota that the HF
    cache blows immediately. This helper does NOT exist in 08.
  - `model._resolve_source()` raises only when `HF_MODEL` is EMPTY
    (not when a local directory is missing — the template is online
    by design).
  - Gated-model loads honor `HF_TOKEN`.

No network, no model loading, no transformers-from-pretrained calls.
"""
from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from hf_hub_streaming import config, model


# --------------------------------------------------------------------------
# config — same pattern as 08 but retained so the test file is self-contained.
# --------------------------------------------------------------------------
def test_defaults():
    assert config.data_dir()
    assert config.hf_model_id()


def test_config_reads_env(monkeypatch):
    monkeypatch.setenv("HF_MODEL", "my-org/my-model")
    assert config.hf_model_id() == "my-org/my-model"


# --------------------------------------------------------------------------
# No MODEL_DIR — 09 is online-first. If this assertion ever flips, 09 has
# drifted into 08's offline-bundled pattern.
# --------------------------------------------------------------------------
def test_no_model_dir_constant():
    assert not hasattr(model, "MODEL_DIR")


# --------------------------------------------------------------------------
# _resolve_source — raises on EMPTY model id, not on missing directory.
# --------------------------------------------------------------------------
def test_resolve_source_returns_model_id(monkeypatch):
    monkeypatch.setenv("HF_MODEL", "google/gemma-2-2b-it")
    assert model._resolve_source() == "google/gemma-2-2b-it"


def test_resolve_source_raises_on_empty_hf_model(monkeypatch):
    monkeypatch.setenv("HF_MODEL", "")
    # The config fallback default ("google/gemma-2-2b-it") kicks in, so
    # to reach the error path we also need to stub config.hf_model_id.
    monkeypatch.setattr(model.config, "hf_model_id", lambda: "")
    with pytest.raises(RuntimeError, match="HF_MODEL"):
        model._resolve_source()


# --------------------------------------------------------------------------
# _check_hf_home — the cluster-safety warning helper. Unique to 09.
# --------------------------------------------------------------------------
def test_check_hf_home_warns_when_unset(monkeypatch):
    monkeypatch.delenv("HF_HOME", raising=False)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        model._check_hf_home()
    msgs = [str(w.message) for w in caught]
    assert any("HF_HOME" in m for m in msgs)


def test_check_hf_home_warns_when_under_cephyr(monkeypatch):
    monkeypatch.setenv("HF_HOME", "/cephyr/users/alice/.cache/huggingface")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        model._check_hf_home()
    msgs = [str(w.message) for w in caught]
    assert any("Cephyr" in m or "60k" in m or "quota" in m for m in msgs)


def test_check_hf_home_silent_when_on_mimer(monkeypatch):
    monkeypatch.setenv("HF_HOME", "/mimer/NOBACKUP/groups/proj/hf-cache")
    # Also override Path.home() so the "startswith($HOME)" branch doesn't
    # spuriously fire on a test runner whose home happens to contain /mimer.
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/root-does-not-exist")))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        model._check_hf_home()
    assert caught == []


# --------------------------------------------------------------------------
# 08 has no _check_hf_home; 09 MUST have it. This guards against drift.
# --------------------------------------------------------------------------
def test_check_hf_home_helper_exists():
    assert callable(getattr(model, "_check_hf_home", None))


# --------------------------------------------------------------------------
# dtype mapping — same as 08 but retained for self-containment.
# --------------------------------------------------------------------------
def test_dtype_resolution_auto_is_preserved(monkeypatch):
    monkeypatch.setenv("HF_DTYPE", "auto")
    assert model._resolve_dtype() == "auto"
