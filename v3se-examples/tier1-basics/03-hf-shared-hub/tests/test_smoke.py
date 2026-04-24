"""Smoke tests — no model loading, no torch import, no network.

The thing that makes this template different from 08/09 is that it
loads ONLY from C3SE's pre-mirrored shared hub at
`/mimer/NOBACKUP/Datasets/LLM/huggingface/hub/` — there is deliberately
no fallback to Hub streaming. These tests pin that contract without
actually calling transformers.
"""
from __future__ import annotations

import pytest

from hf_shared_hub import config


# --------------------------------------------------------------------------- #
# config — defaults + env overrides                                           #
# --------------------------------------------------------------------------- #

def test_defaults(monkeypatch):
    for var in ("HF_MODEL", "HF_MODEL_SNAPSHOT", "HF_DEVICE", "HF_DTYPE",
                "HF_MAX_NEW_TOKENS"):
        monkeypatch.delenv(var, raising=False)
    assert config.data_dir()
    # HF_MODEL default is a small instruct model so the sample fits on T4.
    assert config.hf_model_id() == "google/gemma-2-2b-it"
    # Shared-hub mode: snapshot is None until the user picks one.
    assert config.hf_model_snapshot() is None
    # Device/dtype auto-detect by default.
    assert config.device() == "auto"
    assert config.dtype() == "auto"
    assert config.max_new_tokens() == 200


def test_config_reads_env(monkeypatch):
    monkeypatch.setenv("HF_MODEL", "my-org/my-model")
    assert config.hf_model_id() == "my-org/my-model"


def test_snapshot_points_at_mimer_shared_hub(monkeypatch):
    """HF_MODEL_SNAPSHOT is how users pick a pre-mirrored model — the
    value should flow through verbatim so it can be a real Mimer path."""
    mimer_path = (
        "/mimer/NOBACKUP/Datasets/LLM/huggingface/hub/"
        "models--google--gemma-2-2b-it/snapshots/abc123"
    )
    monkeypatch.setenv("HF_MODEL_SNAPSHOT", mimer_path)
    assert config.hf_model_snapshot() == mimer_path


def test_snapshot_is_none_when_empty(monkeypatch):
    """Empty string must resolve to None (not '') so `model._resolve_source()`
    can do a clean `if not snap:` check without falsy-string pitfalls."""
    monkeypatch.setenv("HF_MODEL_SNAPSHOT", "")
    assert config.hf_model_snapshot() is None


def test_max_new_tokens_is_parsed_as_int(monkeypatch):
    monkeypatch.setenv("HF_MAX_NEW_TOKENS", "512")
    got = config.max_new_tokens()
    assert got == 512
    assert isinstance(got, int)


# --------------------------------------------------------------------------- #
# model._resolve_source — shared-hub is REQUIRED (no Hub fallback)            #
# --------------------------------------------------------------------------- #

def test_resolve_source_requires_snapshot(monkeypatch):
    """The unique contract of this template: `HF_MODEL_SNAPSHOT` unset must
    raise with a pointer to the Mimer shared hub. No silent Hub download."""
    # Import lazily so the error path doesn't need real torch weights.
    pytest.importorskip("torch")
    from hf_shared_hub import model as model_mod

    monkeypatch.delenv("HF_MODEL_SNAPSHOT", raising=False)
    with pytest.raises(RuntimeError, match="HF_MODEL_SNAPSHOT"):
        model_mod._resolve_source()


def test_resolve_source_rejects_missing_path(monkeypatch, tmp_path):
    """Even when HF_MODEL_SNAPSHOT is set, the path must actually exist —
    caught here so users see a clear message instead of a cryptic
    transformers "config.json not found"."""
    pytest.importorskip("torch")
    from hf_shared_hub import model as model_mod

    missing = tmp_path / "does-not-exist"
    monkeypatch.setenv("HF_MODEL_SNAPSHOT", str(missing))
    with pytest.raises(RuntimeError, match="does not exist"):
        model_mod._resolve_source()
