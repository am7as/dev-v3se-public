"""Smoke tests: verify UNIQUE behavior of 11-multi-provider-inference.

No model loading, no network, no GPU — pure config + registry checks.
"""
from __future__ import annotations

from unittest import mock

import pytest

from infer_multi import config, providers, router


# ---------- registry ----------

def test_provider_registry_exposes_all_six():
    """All six shipped providers register: 2 cloud APIs + 1 CLI sub +
    2 local servers + 1 cluster server."""
    assert set(providers.available()) == {
        "openai", "gemini", "claude_cli", "lmstudio", "ollama", "vllm",
    }


def test_provider_lookup_returns_module_with_matching_name():
    for name in ("openai", "gemini", "claude_cli", "lmstudio", "ollama", "vllm"):
        mod = providers.get(name)
        assert mod.NAME == name
        assert hasattr(mod, "predict"), f"{name} missing predict()"


def test_unknown_provider_raises_with_known_list():
    with pytest.raises(ValueError, match="Unknown provider"):
        providers.get("gpt99")


# ---------- default provider / env routing ----------

def test_default_provider_reads_env(monkeypatch):
    monkeypatch.setenv("DEFAULT_PROVIDER", "vllm")
    assert config.default_provider() == "vllm"


def test_default_provider_falls_back_to_openai(monkeypatch):
    monkeypatch.delenv("DEFAULT_PROVIDER", raising=False)
    assert config.default_provider() == "openai"


def test_router_dispatches_to_named_provider(monkeypatch):
    """router.predict(provider=X) must call providers.get(X).predict, not the default."""
    fake = mock.MagicMock(predict=mock.MagicMock(return_value={"text": "hi", "model": "m"}))
    with mock.patch.object(providers, "get", return_value=fake) as getter:
        out = router.predict("hello", provider="vllm", model="test-model")
    getter.assert_called_once_with("vllm")
    fake.predict.assert_called_once_with("hello", model="test-model")
    assert out["text"] == "hi"


def test_router_uses_default_when_no_provider(monkeypatch):
    monkeypatch.setenv("DEFAULT_PROVIDER", "claude_cli")
    fake = mock.MagicMock(predict=mock.MagicMock(return_value={"text": "ok"}))
    with mock.patch.object(providers, "get", return_value=fake) as getter:
        router.predict("hi")
    getter.assert_called_once_with("claude_cli")


# ---------- provider-specific env handling ----------

def test_openai_provider_raises_when_no_key_and_no_base_url(monkeypatch):
    """openai_api requires OPENAI_API_KEY unless OPENAI_BASE_URL is set
    (the latter means we're talking to a local OpenAI-compatible server)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        providers.get("openai").predict("hi")


def test_vllm_provider_raises_when_port_unresolvable(monkeypatch, tmp_path):
    """vllm provider must resolve a port from env or from $RESULTS_DIR/vllm-port.txt.
    With neither present, it raises — no silent fallback to localhost:8000."""
    monkeypatch.delenv("VLLM_PORT", raising=False)
    monkeypatch.delenv("VLLM_HOST", raising=False)
    monkeypatch.setenv("VLLM_PORT_FILE", str(tmp_path / "does-not-exist.txt"))
    monkeypatch.setenv("VLLM_HOST_FILE", str(tmp_path / "no-host.txt"))
    with pytest.raises(RuntimeError, match="VLLM port"):
        providers.get("vllm").predict("hi")


def test_vllm_reads_port_from_file(monkeypatch, tmp_path):
    """Port-file handshake is the Alvis-specific pattern (vllm-server.sbatch
    writes the file, client reads it)."""
    port_file = tmp_path / "vllm-port.txt"
    port_file.write_text("12345\n")
    host_file = tmp_path / "vllm-host.txt"
    host_file.write_text("alvis-gpu-01\n")
    monkeypatch.delenv("VLLM_PORT", raising=False)
    monkeypatch.delenv("VLLM_HOST", raising=False)
    monkeypatch.setenv("VLLM_PORT_FILE", str(port_file))
    monkeypatch.setenv("VLLM_HOST_FILE", str(host_file))

    from infer_multi.providers import vllm as vllm_mod
    host, port = vllm_mod._read_port()
    assert host == "alvis-gpu-01"
    assert port == 12345


def test_claude_cli_raises_when_binary_missing(monkeypatch):
    """claude_cli must fail loudly if the `claude` binary is not on PATH —
    otherwise the subprocess would die with a cryptic error later."""
    monkeypatch.setenv("CLAUDE_CLI_PATH", "/nonexistent/claude-binary-xyz")
    with pytest.raises(RuntimeError, match="Claude CLI"):
        providers.get("claude_cli").predict("hi")


def test_gemini_provider_raises_when_no_key(monkeypatch):
    """gemini provider must fail loudly when neither GEMINI_API_KEY nor
    GOOGLE_API_KEY is set — otherwise the SDK would 401 later."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        providers.get("gemini").predict("hi")


def test_lmstudio_provider_raises_when_no_model(monkeypatch):
    """lmstudio talks to a local server that doesn't validate keys, but
    the SDK requires a model id — surface a clear error if unset."""
    monkeypatch.delenv("LMSTUDIO_MODEL", raising=False)
    with pytest.raises(RuntimeError, match="LMSTUDIO_MODEL"):
        providers.get("lmstudio").predict("hi")


def test_ollama_provider_raises_when_no_model(monkeypatch):
    """ollama similarly needs a pulled model id."""
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    with pytest.raises(RuntimeError, match="OLLAMA_MODEL"):
        providers.get("ollama").predict("hi")
