"""Smoke tests for the Ollama cluster-server template.

These tests exercise behavior UNIQUE to Ollama vs. its sibling 06-lmstudio:
  - `client.make_client` reads `ollama-host.txt` / `ollama-port.txt`
    (NOT `lmstudio-host.txt`).
  - Default API key when none supplied is `"ollama"` (Ollama ignores it
    on its OpenAI-compatible endpoint; we pick a readable sentinel).
  - `client.predict` falls back to the `OLLAMA_MODEL` env var, whose
    default is an Ollama tag (`llama3.1:8b`) — the `name:tag` syntax
    is Ollama-specific and is NOT an HF repo id.
  - The standard Ollama API listens on port 11434; the OpenAI-compatible
    endpoint is served from the same port under `/v1`.

No network, no model loading, no real OpenAI calls.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ollama_cluster import client, config, providers


# --------------------------------------------------------------------------
# config — shared with 06, but we still sanity-check the module loads.
# --------------------------------------------------------------------------
def test_config_has_defaults():
    assert config.data_dir()
    assert config.openai_model()


def test_provider_module_loads():
    assert providers.predict
    assert hasattr(providers, "__all__")


# --------------------------------------------------------------------------
# client._read_endpoint — reads Ollama-specific filenames and produces
# the `/v1` suffix that Ollama's OpenAI-compat shim requires.
# --------------------------------------------------------------------------
def test_read_endpoint_reads_ollama_files(tmp_path):
    (tmp_path / "ollama-host.txt").write_text("alvis4-07\n")
    # 11434 is Ollama's default listener port.
    (tmp_path / "ollama-port.txt").write_text("11434\n")
    host, port = client._read_endpoint(tmp_path)
    assert host == "alvis4-07"
    assert port == 11434


def test_read_endpoint_missing_files_raises(tmp_path):
    # Create the LM Studio filenames on purpose; the Ollama client must
    # NOT accept them as a substitute.
    (tmp_path / "lmstudio-host.txt").write_text("alvis4-07\n")
    (tmp_path / "lmstudio-port.txt").write_text("1234\n")
    with pytest.raises(RuntimeError, match="ollama-host.txt|ollama-port.txt"):
        client._read_endpoint(tmp_path)


def test_make_client_constructs_v1_url_from_endpoint_files(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path))
    (tmp_path / "ollama-host.txt").write_text("alvis4-07")
    (tmp_path / "ollama-port.txt").write_text("11434")

    with patch("ollama_cluster.client.OpenAI") as MockOpenAI:
        client.make_client()

    _, kwargs = MockOpenAI.call_args
    # Ollama's OpenAI-compat endpoint lives at http://host:port/v1 .
    assert kwargs["base_url"] == "http://alvis4-07:11434/v1"


# --------------------------------------------------------------------------
# client.make_client — Ollama-specific default api_key.
# --------------------------------------------------------------------------
def test_make_client_default_api_key_is_ollama(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    with patch("ollama_cluster.client.OpenAI") as MockOpenAI:
        client.make_client(base_url="http://localhost:11434/v1")
    # Ollama ignores the key but the SDK requires one — the template
    # picks "ollama" as its readable sentinel.
    MockOpenAI.assert_called_once_with(
        base_url="http://localhost:11434/v1",
        api_key="ollama",
    )


# --------------------------------------------------------------------------
# client.predict — Ollama-specific model default + tag syntax.
# --------------------------------------------------------------------------
def test_predict_defaults_to_ollama_tag(monkeypatch):
    """Default model uses Ollama's `name:tag` syntax, NOT an HF repo id."""
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    fake_client = MagicMock()
    fake_resp = MagicMock()
    fake_resp.choices[0].message.content = "ok"
    fake_resp.model = "llama3.1:8b"
    fake_resp.usage.model_dump.return_value = {"prompt_tokens": 1}
    fake_resp.model_dump.return_value = {}
    fake_client.chat.completions.create.return_value = fake_resp

    with patch("ollama_cluster.client.make_client", return_value=fake_client):
        client.predict("hello")

    sent = fake_client.chat.completions.create.call_args.kwargs
    assert sent["model"] == "llama3.1:8b"
    # Ollama tag convention: "<name>:<tag>", no "<org>/<repo>".
    assert ":" in sent["model"]
    assert "/" not in sent["model"]


def test_predict_reads_ollama_model_env(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "mistral:7b")
    fake_client = MagicMock()
    fake_resp = MagicMock()
    fake_resp.choices[0].message.content = "ok"
    fake_resp.model = "x"
    fake_resp.usage = None
    fake_resp.model_dump.return_value = {}
    fake_client.chat.completions.create.return_value = fake_resp

    with patch("ollama_cluster.client.make_client", return_value=fake_client):
        client.predict("hi")

    sent = fake_client.chat.completions.create.call_args.kwargs
    assert sent["model"] == "mistral:7b"


# --------------------------------------------------------------------------
# providers.openai — shared plumbing, same negative path as 06.
# --------------------------------------------------------------------------
def test_predict_raises_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        providers.predict("hi")
