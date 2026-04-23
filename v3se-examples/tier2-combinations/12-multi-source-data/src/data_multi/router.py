"""Resolve (source, dataset) → a readable location."""
from __future__ import annotations

from pathlib import Path

from . import config, sources


def resolve(source: str | None = None, dataset: str | None = None) -> Path:
    name = source or config.source()
    mod = sources.get(name)
    return mod.resolve(dataset)
