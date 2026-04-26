"""Google Gemini provider via the unified `google-genai` SDK.

Reads `GEMINI_API_KEY` (preferred) or `GOOGLE_API_KEY` (fallback that the
SDK itself honours). Default model is `gemini-2.5-flash` — current
stable free-tier flash; override with `GEMINI_MODEL` (e.g.
`gemini-flash-latest` to auto-track the alias, or `gemini-2.5-pro`
for higher reasoning).

Gemini 2.5 models do internal "thinking" (chain-of-thought) by default,
charged against your token quota even though those tokens aren't
returned in the response text. Set `GEMINI_THINKING_BUDGET` to control:
  -1  → unlimited (model decides; default for 2.5)
   0  → disable thinking (cheapest; behaves like 2.0/1.5)
  >0  → cap at N thinking tokens
"""
from __future__ import annotations

import os
from typing import Any

NAME = "gemini"


def _client():
    from google import genai
    key = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY is unset (also tried GOOGLE_API_KEY). "
            "Set it in .env or the environment."
        )
    return genai.Client(api_key=key)


def _thinking_config():
    """Build a ThinkingConfig from GEMINI_THINKING_BUDGET, or None to use SDK default."""
    raw = os.environ.get("GEMINI_THINKING_BUDGET", "")
    if not raw:
        return None
    try:
        budget = int(raw)
    except ValueError:
        return None
    from google.genai import types
    return types.ThinkingConfig(thinking_budget=budget)


def predict(prompt: str, *, model: str | None = None, **kw: Any) -> dict[str, Any]:
    c = _client()
    m = model or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    tc = _thinking_config()
    if tc is not None and "config" not in kw:
        from google.genai import types
        kw["config"] = types.GenerateContentConfig(thinking_config=tc)
    resp = c.models.generate_content(model=m, contents=prompt, **kw)
    u = getattr(resp, "usage_metadata", None)
    return {
        "text":  resp.text or "",
        "raw":   resp.model_dump() if hasattr(resp, "model_dump") else str(resp),
        "model": m,
        "usage": {
            "prompt_tokens":     getattr(u, "prompt_token_count",     0) if u else 0,
            "completion_tokens": getattr(u, "candidates_token_count", 0) if u else 0,
            "total_tokens":      getattr(u, "total_token_count",      0) if u else 0,
        },
    }
