"""OpenAI-compatible provider (OpenAI, Azure, LM Studio, Ollama, vLLM, ...)."""
from __future__ import annotations

import os
from typing import Any

from openai import OpenAI

NAME = "openai"


def _client() -> OpenAI:
    key = os.environ.get("OPENAI_API_KEY", "")
    base = os.environ.get("OPENAI_BASE_URL", "") or None
    if not key:
        # Local OpenAI-compatible servers (LM Studio, Ollama) ignore the key
        # but SDK requires something non-empty.
        key = "not-needed" if base else ""
    if not key:
        raise RuntimeError("OPENAI_API_KEY is unset (and no OPENAI_BASE_URL).")
    return OpenAI(api_key=key, base_url=base) if base else OpenAI(api_key=key)


def predict(prompt: str, *, model: str | None = None, **kw: Any) -> dict[str, Any]:
    c = _client()
    m = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
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
