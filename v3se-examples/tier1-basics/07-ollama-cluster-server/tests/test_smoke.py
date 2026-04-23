from ollama_cluster import config, providers


def test_config_has_defaults():
    assert config.data_dir()
    assert config.openai_model()


def test_provider_module_loads():
    assert providers.predict
    assert hasattr(providers, "__all__")


def test_predict_raises_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import pytest
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        providers.predict("hi")
