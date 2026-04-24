"""Smoke tests — no network, no real API calls.

The unique thing about this template is the OpenAI-compatible provider:
it must accept a custom `OPENAI_BASE_URL` (so the same code drives
openai.com, Azure, LM Studio, or vLLM) and fail loudly when the key
is missing.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from infer_api import config, providers


# --------------------------------------------------------------------------- #
# config — env-driven defaults                                                #
# --------------------------------------------------------------------------- #

def test_config_has_defaults(monkeypatch):
    """With no OPENAI_MODEL set, config falls back to gpt-4o-mini — the
    cheapest sensible default for a blank template."""
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    assert config.data_dir()
    assert config.openai_model() == "gpt-4o-mini"


def test_openai_model_reads_env(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
    assert config.openai_model() == "gpt-4o"


def test_openai_base_url_is_none_by_default(monkeypatch):
    """Unset base URL must be None (not '') so the OpenAI client skips it
    and talks to api.openai.com — anything else would break Azure routing."""
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    assert config.openai_base_url() is None


def test_openai_base_url_supports_local_endpoint(monkeypatch):
    """LM Studio / vLLM on-cluster use the OpenAI shape at a custom URL."""
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:1234/v1")
    assert config.openai_base_url() == "http://localhost:1234/v1"


# --------------------------------------------------------------------------- #
# providers — registry shape + failure modes                                  #
# --------------------------------------------------------------------------- #

def test_provider_registry_exposes_only_openai():
    """This template is single-provider by design (11-multi-provider-inference
    is the multi one). The registry must not grow other names silently."""
    assert callable(providers.predict)
    assert providers.__all__ == ["predict"]


def test_predict_raises_without_key(monkeypatch):
    """Missing OPENAI_API_KEY must fail fast with a message that names the
    env var — users shouldn't have to read a stack trace to find it."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        providers.predict("hi")


def test_predict_passes_base_url_to_client(monkeypatch):
    """The provider must hand OPENAI_BASE_URL through to the OpenAI client —
    that's what makes the LM Studio / Azure / vLLM swap possible without
    any code change."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:1234/v1")
    with patch("infer_api.providers.openai.OpenAI") as mock_openai:
        mock_openai.return_value.chat.completions.create.side_effect = RuntimeError("stop here")
        with pytest.raises(RuntimeError, match="stop here"):
            providers.predict("hi")
        mock_openai.assert_called_once()
        kwargs = mock_openai.call_args.kwargs
        assert kwargs.get("api_key") == "sk-test-123"
        assert kwargs.get("base_url") == "http://localhost:1234/v1"


def test_predict_omits_base_url_when_unset(monkeypatch):
    """When OPENAI_BASE_URL is absent, we must call OpenAI() WITHOUT a
    base_url kwarg — passing base_url=None breaks Azure routing."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    with patch("infer_api.providers.openai.OpenAI") as mock_openai:
        mock_openai.return_value.chat.completions.create.side_effect = RuntimeError("stop here")
        with pytest.raises(RuntimeError, match="stop here"):
            providers.predict("hi")
        kwargs = mock_openai.call_args.kwargs
        assert "base_url" not in kwargs
        assert kwargs.get("api_key") == "sk-test-123"
