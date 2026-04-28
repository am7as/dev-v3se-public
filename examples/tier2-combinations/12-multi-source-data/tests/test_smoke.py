"""Smoke tests: verify UNIQUE behavior of 12-multi-source-data.

This example routes dataset reads across 5 sources: local, cephyr_private,
mimer_shared, hf_hub, gcs. Each source module exposes NAME + resolve();
router.resolve(source, dataset) dispatches to the right one.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from data_multi import config, router, sources


# ---------- registry ----------

def test_sources_registry_exposes_all_five():
    """All five shipped sources must register."""
    assert set(sources.available()) == {
        "local", "cephyr_private", "mimer_shared", "hf_hub", "gcs",
    }


def test_every_source_module_has_name_and_resolve():
    for name in sources.available():
        mod = sources.get(name)
        assert mod.NAME == name
        assert callable(getattr(mod, "resolve", None)), f"{name} missing resolve()"


def test_unknown_source_raises():
    with pytest.raises(ValueError, match="Unknown source"):
        sources.get("cephyr_shared")  # old name, now renamed to mimer_shared


def test_mimer_shared_not_cephyr_shared():
    """Regression: the shared area is called `mimer_shared`, not `cephyr_shared`."""
    avail = sources.available()
    assert "mimer_shared" in avail
    assert "cephyr_shared" not in avail


# ---------- source dispatch ----------

def test_default_source_is_local(monkeypatch):
    monkeypatch.delenv("DATASET_SOURCE", raising=False)
    assert config.source() == "local"


def test_source_env_override(monkeypatch):
    monkeypatch.setenv("DATASET_SOURCE", "mimer_shared")
    assert config.source() == "mimer_shared"


def test_router_resolves_with_env_default(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATASET_SOURCE", "local")
    assert router.resolve() == tmp_path


def test_router_resolves_with_dataset_suffix(monkeypatch, tmp_path):
    """Local / cephyr_private / mimer_shared all append the dataset name to DATA_DIR."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    for src in ("local", "cephyr_private", "mimer_shared"):
        assert router.resolve(src, dataset="my-ds") == tmp_path / "my-ds"


# ---------- source-specific behavior ----------

def test_hf_hub_resolves_to_cache_dir(monkeypatch):
    """hf_hub.resolve() returns a cache path under HF_HOME, NOT under DATA_DIR —
    the Hub source lives in a different tree from the file-backed sources."""
    monkeypatch.setenv("HF_HOME", "/workspace/.hf-cache")
    p = router.resolve("hf_hub")
    assert "hf-cache" in str(p)
    assert str(p).endswith("datasets")


def test_gcs_resolves_to_fuse_mount_point():
    """gcs.resolve() returns the rclone FUSE mount point, not a real filesystem path.
    Caller must invoke gcs.mount() separately."""
    p = router.resolve("gcs")
    assert str(p).replace("\\", "/") == "/tmp/gcs-mount"


def test_gcs_mount_requires_remote_env(monkeypatch):
    """gcs.mount() without GCS_RCLONE_REMOTE fails fast."""
    monkeypatch.delenv("GCS_RCLONE_REMOTE", raising=False)
    from data_multi.sources import gcs
    with pytest.raises(RuntimeError, match="GCS_RCLONE_REMOTE"):
        gcs.mount()


def test_results_dir_default(monkeypatch):
    monkeypatch.delenv("RESULTS_DIR", raising=False)
    assert str(config.results_dir()).replace("\\", "/") == "/results"
