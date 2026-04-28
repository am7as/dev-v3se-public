"""Smoke tests for the LM Studio cluster-server template.

These tests exercise behavior UNIQUE to LM Studio vs. its sibling 07-ollama:
  - `client.make_client` reads `lmstudio-host.txt` / `lmstudio-port.txt`
    (NOT `ollama-host.txt`).
  - Default API key when none supplied is `"lm-studio"` (LM Studio accepts
    any non-empty key; we pick a readable sentinel).
  - `client.predict` falls back to the `LMSTUDIO_MODEL` env var, whose
    default is an HF-style repo id (`lmstudio-community/...`), NOT an
    Ollama tag like `llama3:latest`.

No network, no model loading, no real OpenAI calls.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lmstudio_cluster import client, config, providers


# --------------------------------------------------------------------------
# config — shared with 07, but we still sanity-check the module loads.
# --------------------------------------------------------------------------
def test_config_has_defaults():
    assert config.data_dir()
    assert config.openai_model()


def test_provider_module_loads():
    assert providers.predict
    assert hasattr(providers, "__all__")


# --------------------------------------------------------------------------
# client._read_endpoint — reads LM-Studio-specific filenames.
# --------------------------------------------------------------------------
def test_read_endpoint_reads_lmstudio_files(tmp_path):
    (tmp_path / "lmstudio-host.txt").write_text("alvis3-04\n")
    (tmp_path / "lmstudio-port.txt").write_text("1234\n")
    host, port = client._read_endpoint(tmp_path)
    assert host == "alvis3-04"
    assert port == 1234


def test_read_endpoint_missing_files_raises(tmp_path):
    # Create the Ollama-style names on purpose; the LM Studio client
    # must NOT accept them.
    (tmp_path / "ollama-host.txt").write_text("alvis3-04\n")
    (tmp_path / "ollama-port.txt").write_text("11434\n")
    with pytest.raises(RuntimeError, match="lmstudio-host.txt|lmstudio-port.txt"):
        client._read_endpoint(tmp_path)


# --------------------------------------------------------------------------
# client.make_client — base-url resolution + LM-Studio-specific api_key default.
# --------------------------------------------------------------------------
def test_make_client_uses_explicit_base_url_and_default_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    with patch("lmstudio_cluster.client.OpenAI") as MockOpenAI:
        client.make_client(base_url="http://localhost:1234/v1")
    # LM Studio accepts any key; the code picks "lm-studio" as its sentinel.
    MockOpenAI.assert_called_once_with(
        base_url="http://localhost:1234/v1",
        api_key="lm-studio",
    )


def test_make_client_reads_openai_base_url_env(monkeypatch, tmp_path):
    # With OPENAI_BASE_URL set (e.g. SSH port-forward from laptop),
    # the client must NOT try to read the host/port files.
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:7777/v1")
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path))  # empty dir — would raise if read
    with patch("lmstudio_cluster.client.OpenAI") as MockOpenAI:
        client.make_client()
    _, kwargs = MockOpenAI.call_args
    assert kwargs["base_url"] == "http://localhost:7777/v1"


# --------------------------------------------------------------------------
# client.predict — LM-Studio-specific model default + env override.
# --------------------------------------------------------------------------
def test_predict_defaults_to_lmstudio_model_env(monkeypatch):
    """Default model is HF-style (lmstudio-community/...), NOT an Ollama tag."""
    monkeypatch.delenv("LMSTUDIO_MODEL", raising=False)

    fake_client = MagicMock()
    fake_resp = MagicMock()
    fake_resp.choices[0].message.content = "ok"
    fake_resp.model = "lmstudio-community/llama-3.1-8b-instruct"
    fake_resp.usage.model_dump.return_value = {"prompt_tokens": 1}
    fake_resp.model_dump.return_value = {}
    fake_client.chat.completions.create.return_value = fake_resp

    with patch("lmstudio_cluster.client.make_client", return_value=fake_client):
        client.predict("hello")

    sent = fake_client.chat.completions.create.call_args.kwargs
    assert sent["model"] == "lmstudio-community/llama-3.1-8b-instruct"
    # HF-style id convention: "<org>/<repo>", no colon-tag.
    assert "/" in sent["model"]
    assert ":" not in sent["model"]


def test_predict_reads_lmstudio_model_env(monkeypatch):
    monkeypatch.setenv("LMSTUDIO_MODEL", "TheBloke/Mistral-7B-Instruct-v0.2-GGUF")
    fake_client = MagicMock()
    fake_resp = MagicMock()
    fake_resp.choices[0].message.content = "ok"
    fake_resp.model = "x"
    fake_resp.usage = None
    fake_resp.model_dump.return_value = {}
    fake_client.chat.completions.create.return_value = fake_resp

    with patch("lmstudio_cluster.client.make_client", return_value=fake_client):
        client.predict("hi")

    sent = fake_client.chat.completions.create.call_args.kwargs
    assert sent["model"] == "TheBloke/Mistral-7B-Instruct-v0.2-GGUF"


# --------------------------------------------------------------------------
# providers.openai — shared plumbing, same negative path as 07.
# --------------------------------------------------------------------------
def test_predict_raises_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        providers.predict("hi")
