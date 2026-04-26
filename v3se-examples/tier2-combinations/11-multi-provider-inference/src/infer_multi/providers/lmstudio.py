"""LM Studio local-server provider — wraps the openai SDK with the
LM Studio HTTP endpoint.

Defaults to LMSTUDIO_BASE_URL=http://host.docker.internal:1234/v1
(the LM Studio default port, reachable from inside Docker on
laptop). On Alvis, the `lmstudio-server.sbatch` writes the running
host:port into `$RESULTS_DIR/lmstudio-port.txt` and the client reads
that — see `06-lmstudio-cluster-server` for the pattern.
"""
from __future__ import annotations

import os
from typing import Any

from openai import OpenAI

NAME = "lmstudio"


def _client() -> OpenAI:
    base = os.environ.get("LMSTUDIO_BASE_URL", "") or "http://host.docker.internal:1234/v1"
    # LM Studio doesn't validate the API key but the SDK requires one.
    return OpenAI(api_key="not-needed", base_url=base)


def predict(prompt: str, *, model: str | None = None, **kw: Any) -> dict[str, Any]:
    c = _client()
    m = model or os.environ.get("LMSTUDIO_MODEL", "")
    if not m:
        raise RuntimeError(
            "LMSTUDIO_MODEL is unset. Set it to the loaded model's id "
            "(see LM Studio → Models → Loaded)."
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
