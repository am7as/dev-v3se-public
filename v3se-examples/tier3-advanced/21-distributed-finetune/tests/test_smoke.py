from dist_ft import config


def test_defaults():
    assert config.model_id()
    assert config.dataset_id() == "tatsu-lab/alpaca"


def test_training_hyperparams(monkeypatch):
    monkeypatch.setenv("PER_DEVICE_BATCH", "8")
    monkeypatch.setenv("GRAD_ACCUM", "16")
    assert config.per_device_batch() == 8
    assert config.grad_accum() == 16
