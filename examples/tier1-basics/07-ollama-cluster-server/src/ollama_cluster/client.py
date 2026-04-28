"""Ollama client — reads host:port from cluster job outputs, calls OpenAI-compatible API."""

from __future__ import annotations

import os
from pathlib import Path

from openai import OpenAI


def _read_endpoint(results_dir: Path) -> tuple[str, int]:
    """Read host:port written by the ollama-server sbatch."""
    host_file = results_dir / "ollama-host.txt"
    port_file = results_dir / "ollama-port.txt"
    if not (host_file.exists() and port_file.exists()):
        raise RuntimeError(
            f"Missing {host_file} or {port_file}. "
            "The cluster ollama-server job probably isn't running yet."
        )
    return host_file.read_text().strip(), int(port_file.read_text().strip())


def make_client(base_url: str | None = None) -> OpenAI:
    """Return an OpenAI client pointed at the Ollama server.

    Resolution order:
      1. explicit `base_url` argument
      2. `OPENAI_BASE_URL` env var (set this when using SSH port-forward)
      3. read `$RESULTS_DIR/ollama-{host,port}.txt` (only useful when
         this client runs on the cluster itself alongside the server)
    """
    if base_url is None:
        base_url = os.environ.get("OPENAI_BASE_URL")
    if base_url is None:
        results_dir = Path(os.environ.get("RESULTS_DIR", "./results"))
        host, port = _read_endpoint(results_dir)
        base_url = f"http://{host}:{port}/v1"

    api_key = os.environ.get("OPENAI_API_KEY", "ollama")
    return OpenAI(base_url=base_url, api_key=api_key)


def predict(prompt: str, model: str | None = None, **kwargs) -> dict:
    """Uniform `predict()` signature matching other providers."""
    client = make_client()
    model = model or os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        **kwargs,
    )
    return {
        "text": resp.choices[0].message.content,
        "raw": resp.model_dump(),
        "model": resp.model,
        "usage": resp.usage.model_dump() if resp.usage else {},
    }
