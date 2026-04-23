"""Smoke tests that DO NOT load the model (keeps CI fast)."""
from hf_sif_bundle import config


def test_defaults():
    assert config.data_dir()
    assert config.hf_model_id()


def test_config_reads_env(monkeypatch):
    monkeypatch.setenv("HF_MODEL", "my-org/my-model")
    assert config.hf_model_id() == "my-org/my-model"


def test_snapshot_precedence(monkeypatch):
    monkeypatch.setenv("HF_MODEL_SNAPSHOT", "/mimer/x")
    assert config.hf_model_snapshot() == "/mimer/x"
