"""Fast tests — don't actually train."""
from train_lora import config


def test_config_defaults():
    assert config.model_id() == "sshleifer/tiny-gpt2"
    assert config.lora_r() == 8
    assert config.num_epochs() == 1


def test_config_overrides(monkeypatch):
    monkeypatch.setenv("LORA_R", "32")
    monkeypatch.setenv("NUM_EPOCHS", "3")
    assert config.lora_r() == 32
    assert config.num_epochs() == 3
