"""Ollama local-server provider — wraps the openai SDK with the
Ollama HTTP endpoint.

Defaults to OLLAMA_BASE_URL=http://host.docker.internal:11434/v1
(Ollama's OpenAI-compatible port, reachable from inside Docker on
laptop). On Alvis, the `ollama-server.sbatch` writes the running
host:port into `$RESULTS_DIR/ollama-port.txt` — see
`07-ollama-cluster-server` for the pattern.
"""
from __future__ import annotations

import os
from typing import Any

from openai import OpenAI

NAME = "ollama"


def _client() -> OpenAI:
    base = os.environ.get("OLLAMA_BASE_URL", "") or "http://host.docker.internal:11434/v1"
    return OpenAI(api_key="not-needed", base_url=base)


def predict(prompt: str, *, model: str | None = None, **kw: Any) -> dict[str, Any]:
    c = _client()
    m = model or os.environ.get("OLLAMA_MODEL", "")
    if not m:
        raise RuntimeError(
            "OLLAMA_MODEL is unset. Set it to a model you've pulled "
            "(e.g. `ollama pull llama3.2:3b` → OLLAMA_MODEL=llama3.2:3b)."
        )
    resp = c.chat.completions.create(
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
