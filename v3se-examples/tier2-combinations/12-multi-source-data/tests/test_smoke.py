from data_multi import config, sources, router


def test_sources_registry():
    assert set(sources.available()) == {"local", "cephyr_private", "mimer_shared", "hf_hub", "gcs"}


def test_get_source():
    import pytest
    assert sources.get("local").NAME == "local"
    with pytest.raises(ValueError):
        sources.get("nope")


def test_router_default(monkeypatch):
    monkeypatch.setenv("DATA_DIR", "/tmp/test")
    monkeypatch.setenv("DATASET_SOURCE", "local")
    r = router.resolve()
    assert str(r) == "/tmp/test"


def test_router_with_dataset(monkeypatch):
    monkeypatch.setenv("DATA_DIR", "/tmp/test")
    r = router.resolve("local", dataset="sample")
    assert str(r).endswith("sample")
