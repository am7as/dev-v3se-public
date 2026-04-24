"""Fast tests — don't actually train.

The unique thing about this template is the LoRA hyperparameter surface:
rank / alpha / dropout / epochs / batch / lr all come from env vars with
sensible laptop-sized defaults. No GPU, no weights, no datasets.
"""
from __future__ import annotations

import pytest

from train_lora import config


# --------------------------------------------------------------------------- #
# base model selection                                                        #
# --------------------------------------------------------------------------- #

def test_base_model_default_is_tiny(monkeypatch):
    """Default base model must be a tiny CPU-friendly one so `pixi run
    train-local` finishes on a laptop in seconds."""
    monkeypatch.delenv("HF_MODEL", raising=False)
    assert config.model_id() == "sshleifer/tiny-gpt2"


def test_base_model_respects_hf_model_env(monkeypatch):
    """HF_MODEL lets users point at any Hub id (e.g. meta-llama/...)
    without touching the code."""
    monkeypatch.setenv("HF_MODEL", "meta-llama/Llama-3.2-1B")
    assert config.model_id() == "meta-llama/Llama-3.2-1B"


def test_model_snapshot_prefers_local_path(monkeypatch, tmp_path):
    """HF_MODEL_SNAPSHOT (Mimer shared-hub path) is how Alvis users avoid
    a Hub download during a training run."""
    monkeypatch.setenv("HF_MODEL_SNAPSHOT", str(tmp_path))
    assert config.model_snapshot() == str(tmp_path)


def test_model_snapshot_is_none_when_unset(monkeypatch):
    monkeypatch.delenv("HF_MODEL_SNAPSHOT", raising=False)
    assert config.model_snapshot() is None


# --------------------------------------------------------------------------- #
# LoRA hyperparameters                                                        #
# --------------------------------------------------------------------------- #

def test_lora_defaults_are_sensible(monkeypatch):
    """r=8, alpha=16, dropout=0.05 is the canonical QLoRA starting point.
    If anyone quietly changes these, the sample run stops being comparable
    across template bumps."""
    for var in ("LORA_R", "LORA_ALPHA", "LORA_DROPOUT"):
        monkeypatch.delenv(var, raising=False)
    assert config.lora_r() == 8
    assert config.lora_alpha() == 16
    assert config.lora_dropout() == pytest.approx(0.05)
    # alpha/r ratio = 2 is the standard scaling recommendation.
    assert config.lora_alpha() / config.lora_r() == pytest.approx(2.0)


def test_lora_overrides(monkeypatch):
    monkeypatch.setenv("LORA_R", "32")
    monkeypatch.setenv("LORA_ALPHA", "64")
    monkeypatch.setenv("LORA_DROPOUT", "0.1")
    assert config.lora_r() == 32
    assert config.lora_alpha() == 64
    assert config.lora_dropout() == pytest.approx(0.1)


def test_lora_hyperparams_return_correct_types(monkeypatch):
    """Env vars come in as strings — the getters must parse them, otherwise
    peft.LoraConfig(r='8') blows up at runtime."""
    monkeypatch.setenv("LORA_R", "16")
    monkeypatch.setenv("LORA_DROPOUT", "0.25")
    monkeypatch.setenv("LEARNING_RATE", "5e-5")
    assert isinstance(config.lora_r(), int)
    assert isinstance(config.lora_dropout(), float)
    assert isinstance(config.learning_rate(), float)
    assert config.learning_rate() == pytest.approx(5e-5)


# --------------------------------------------------------------------------- #
# training knobs                                                              #
# --------------------------------------------------------------------------- #

def test_training_defaults(monkeypatch):
    """Laptop-safe defaults: 1 epoch, batch 4, lr 1e-4 — finishes in seconds
    on CPU with the 5-row built-in sample."""
    for var in ("NUM_EPOCHS", "BATCH_SIZE", "LEARNING_RATE"):
        monkeypatch.delenv(var, raising=False)
    assert config.num_epochs() == 1
    assert config.batch_size() == 4
    assert config.learning_rate() == pytest.approx(1e-4)


def test_training_overrides(monkeypatch):
    monkeypatch.setenv("NUM_EPOCHS", "3")
    monkeypatch.setenv("BATCH_SIZE", "16")
    assert config.num_epochs() == 3
    assert config.batch_size() == 16


def test_dataset_id_empty_means_in_memory_sample(monkeypatch):
    """Empty HF_DATASET is the signal to use the 5-row built-in sample —
    that's how a fresh clone trains end-to-end without needing dataset
    access."""
    monkeypatch.delenv("HF_DATASET", raising=False)
    assert config.dataset_id() == ""
    monkeypatch.setenv("HF_DATASET", "Abirate/english_quotes")
    assert config.dataset_id() == "Abirate/english_quotes"


# --------------------------------------------------------------------------- #
# paths                                                                       #
# --------------------------------------------------------------------------- #

def test_results_dir_override(monkeypatch, tmp_path):
    """RESULTS_DIR is where the LoRA adapter gets saved — on Alvis this
    typically points at Mimer so the adapter survives the job."""
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path))
    assert config.results_dir() == tmp_path


def test_ensure_results_dir_creates_missing_tree(monkeypatch, tmp_path):
    target = tmp_path / "adapters" / "run-1"
    monkeypatch.setenv("RESULTS_DIR", str(target))
    out = config.ensure_results_dir()
    assert out == target
    assert target.is_dir()
