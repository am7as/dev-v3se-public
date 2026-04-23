from reco import config


def test_defaults():
    assert config.model_id() == "distilbert-base-uncased"
    assert config.dataset_id() == "emotion"
    assert config.num_labels() == 6


def test_overrides(monkeypatch):
    monkeypatch.setenv("HF_MODEL", "bert-base-uncased")
    monkeypatch.setenv("NUM_LABELS", "3")
    assert config.model_id() == "bert-base-uncased"
    assert config.num_labels() == 3
