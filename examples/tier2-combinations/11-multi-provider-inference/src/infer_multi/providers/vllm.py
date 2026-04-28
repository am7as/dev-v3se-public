"""vLLM OpenAI-compatible server client.

Reads the server's host/port from env or from files written by
_shared/slurm/vllm-server.sbatch (`vllm-host.txt`, `vllm-port.txt`
under $RESULTS_DIR).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from openai import OpenAI

NAME = "vllm"


def _read_port() -> tuple[str, int]:
    host = os.environ.get("VLLM_HOST", "") or "localhost"
    port_str = os.environ.get("VLLM_PORT", "")

    if not port_str:
        port_file = os.environ.get("VLLM_PORT_FILE", "/results/vllm-port.txt")
        host_file = os.environ.get("VLLM_HOST_FILE", "/results/vllm-host.txt")
        if Path(port_file).exists():
            port_str = Path(port_file).read_text().strip()
        if Path(host_file).exists():
            host = Path(host_file).read_text().strip()

    if not port_str:
        raise RuntimeError(
            "VLLM port not resolvable. Set VLLM_PORT in .env, or ensure "
            f"{port_file} exists (the vllm-server.sbatch writes it)."
        )
    return host, int(port_str)


def predict(prompt: str, *, model: str | None = None, **kw: Any) -> dict[str, Any]:
    host, port = _read_port()
    client = OpenAI(api_key="not-needed", base_url=f"http://{host}:{port}/v1")
    m = model or os.environ.get("VLLM_MODEL", "google/gemma-2-9b-it")
    resp = client.chat.completions.create(
        model=m, messages=[{"role": "user", "content": prompt}], **kw
    )
    u = resp.usage
    return {
        "text":  resp.choices[0].message.content or "",
        "raw":   resp.model_dump(),
        "model": m,
        "usage": {
            "prompt_tokens":     u.prompt_tokens     if u else 0,
            "completion_tokens": u.completion_tokens if u else 0,
            "total_tokens":      u.total_tokens      if u else 0,
        },
    }
