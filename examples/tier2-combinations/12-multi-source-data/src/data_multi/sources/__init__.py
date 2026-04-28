"""Data source registry — each module exposes NAME and resolve(dataset)."""
from . import cephyr_private, mimer_shared, gcs, hf_hub, local

_SOURCES = {
    m.NAME: m for m in (local, cephyr_private, mimer_shared, hf_hub, gcs)
}


def get(name: str):
    try:
        return _SOURCES[name]
    except KeyError:
        raise ValueError(f"Unknown source '{name}'. Known: {sorted(_SOURCES)}")


def available() -> list[str]:
    return sorted(_SOURCES)
