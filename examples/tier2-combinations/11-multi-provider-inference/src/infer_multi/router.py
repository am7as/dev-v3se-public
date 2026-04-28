"""Route a provider name → predict() function."""
from __future__ import annotations

from typing import Any

from . import config, providers


def predict(prompt: str, *, provider: str | None = None, model: str | None = None,
            **kw: Any) -> dict[str, Any]:
    name = provider or config.default_provider()
    mod = providers.get(name)
    return mod.predict(prompt, model=model, **kw)
