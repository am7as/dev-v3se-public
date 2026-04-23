from infer_multi import config, providers, router


def test_providers_registry():
    assert set(providers.available()) == {"openai", "claude_cli", "vllm"}


def test_get_provider():
    import pytest
    assert providers.get("openai").NAME == "openai"
    with pytest.raises(ValueError, match="Unknown provider"):
        providers.get("nonsense")


def test_router_uses_default(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.setenv("DEFAULT_PROVIDER", "openai")
    import pytest
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        router.predict("hi")
