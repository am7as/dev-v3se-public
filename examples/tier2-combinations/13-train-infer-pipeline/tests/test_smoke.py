"""Smoke tests: verify UNIQUE behavior of 13-train-infer-pipeline.

This example chains train -> bundle -> infer: LoRA finetune, then pack the
adapter plus a baked-in base model into a self-contained SIF via the
bundle.def.tpl template. Tests exercise config overlap (same model id
variable across train + infer), template substitution, and the bundler's
input-validation contract.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from train_infer import bundler, config


# ---------- config (shared between train.py and inference) ----------

def test_model_id_default():
    assert config.model_id() == "sshleifer/tiny-gpt2"


def test_model_snapshot_is_none_by_default(monkeypatch):
    monkeypatch.delenv("HF_MODEL_SNAPSHOT", raising=False)
    assert config.model_snapshot() is None


def test_model_snapshot_takes_precedence_over_model_id(monkeypatch):
    """Train and infer both call _source() -> snapshot or model_id.
    Setting HF_MODEL_SNAPSHOT must override HF_MODEL at both ends."""
    monkeypatch.setenv("HF_MODEL", "some-org/some-model")
    monkeypatch.setenv("HF_MODEL_SNAPSHOT", "/mimer/NOBACKUP/groups/x/snap")
    assert config.model_snapshot() == "/mimer/NOBACKUP/groups/x/snap"


def test_lora_defaults():
    assert config.lora_r() == 8
    assert config.lora_alpha() == 16
    assert config.lora_dropout() == 0.05


def test_results_dir_is_mimer_ready(monkeypatch, tmp_path):
    """RESULTS_DIR is the Mimer target in production. In tests we redirect to tmp_path
    to avoid permission issues; ensure_results_dir() must create it."""
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path / "results"))
    p = config.ensure_results_dir()
    assert p.exists() and p.is_dir()


# ---------- bundle.def.tpl contract ----------

def _tpl_path() -> Path:
    return (Path(__file__).resolve().parents[1] / "apptainer" / "bundle.def.tpl")


def test_bundle_template_exists():
    assert _tpl_path().exists(), "apptainer/bundle.def.tpl must ship with the example"


def test_bundle_template_has_required_placeholders():
    """bundler.build() substitutes ADAPTER_SRC and BASE_MODEL. Both must be present
    in the template, or substitution is a no-op and the resulting SIF breaks."""
    tpl = _tpl_path().read_text()
    assert "ADAPTER_SRC" in tpl
    assert "BASE_MODEL" in tpl


def test_bundle_template_sets_offline_inference_env():
    """Bundled SIFs must run fully offline: HF_HUB_OFFLINE + HF_MODEL_SNAPSHOT
    pointing at the baked-in base dir. This is the whole point of the bundle."""
    tpl = _tpl_path().read_text()
    assert "HF_HUB_OFFLINE" in tpl
    assert "HF_MODEL_SNAPSHOT" in tpl
    assert "TRANSFORMERS_OFFLINE" in tpl


# ---------- bundler validation ----------

def test_bundler_raises_when_adapter_missing(tmp_path):
    """build() must validate adapter existence BEFORE invoking apptainer."""
    with pytest.raises(FileNotFoundError, match="Adapter dir"):
        bundler.build(
            adapter_dir=tmp_path / "no-adapter",
            base_model="dummy/model",
            out_sif=tmp_path / "out.sif",
            tpl_path=tmp_path / "no-tpl.def",
        )


def test_bundler_raises_when_template_missing(tmp_path):
    """build() must validate template existence BEFORE invoking apptainer."""
    adapter = tmp_path / "adapter"
    adapter.mkdir()
    with pytest.raises(FileNotFoundError, match="Bundle template"):
        bundler.build(
            adapter_dir=adapter,
            base_model="dummy/model",
            out_sif=tmp_path / "out.sif",
            tpl_path=tmp_path / "nope.def",
        )


def test_bundler_substitutes_placeholders(monkeypatch, tmp_path):
    """Verify the text-substitution contract without actually running apptainer."""
    # Prepare a fake adapter and a minimal template with both placeholders.
    adapter = tmp_path / "adapter"
    adapter.mkdir()
    tpl = tmp_path / "tpl.def"
    tpl.write_text("ADAPTER=ADAPTER_SRC\nMODEL=BASE_MODEL\n")

    # Stub subprocess.run so the test doesn't need apptainer installed.
    def _fake_run(cmd, check=False, **kw):
        class R:
            returncode = 0
        return R()

    monkeypatch.setattr(bundler.subprocess, "run", _fake_run)

    out_sif = tmp_path / "out.sif"
    bundler.build(adapter, "my-org/my-model", out_sif, tpl_path=tpl)

    # Substituted .def written next to the SIF
    written = out_sif.with_suffix(".def").read_text()
    assert f"ADAPTER={adapter}" in written
    assert "MODEL=my-org/my-model" in written
    # Manifest alongside records what was baked in
    manifest = out_sif.with_suffix(".json").read_text()
    assert "my-org/my-model" in manifest
    assert str(adapter) in manifest
