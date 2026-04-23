"""OpenAI-compatible chat-completion provider.

Works against openai.com, Azure OpenAI (set OPENAI_BASE_URL), and any
OpenAI-compatible server (LM Studio, vLLM) — the API shape is the same.
"""
from __future__ import annotations

import os
from typing import Any

from openai import OpenAI

from .. import config

NAME = "openai"


def _client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is unset. Put it in .env, or set OPENAI_BASE_URL "
            "to a local OpenAI-compatible endpoint with any non-empty key."
        )
    base_url = config.openai_base_url()
    return OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)


def predict(prompt: str, *, model: str | None = None, **kwargs: Any) -> dict[str, Any]:
    """Call the chat API with a single-user-message prompt.

    Returns: {"text", "raw", "model", "usage"} — the canonical provider
    return shape (matches the pattern used across multi-provider templates).
    """
    c = _client()
    model = model or config.openai_model()
    resp = c.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        **kwargs,
    )
    choice = resp.choices[0]
    usage = resp.usage
    return {
        "text":  choice.message.content or "",
        "raw":   resp.model_dump(),
        "model": model,
        "usage": {
            "prompt_tokens":     usage.prompt_tokens     if usage else 0,
            "completion_tokens": usage.completion_tokens if usage else 0,
            "total_tokens":      usage.total_tokens      if usage else 0,
        },
    }
