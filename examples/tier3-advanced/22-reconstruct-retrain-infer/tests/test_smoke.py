"""Smoke tests: verify UNIQUE behavior of 22-reconstruct-retrain-infer.

This example pipelines three phases:
  1. surgery  — mutate architecture (swap classification head, etc.),
                config driven by configs/surgery.yaml
  2. retrain  — fine-tune the surgeried model via accelerate launch
  3. eval     — classifier metrics on the retrained checkpoint

Each phase has its own pixi task + slurm sbatch. Tests verify the phase
wiring, surgery-config parsing, and the accelerate-variant parametrization.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from reco import config, surgery


# ---------- config knobs ----------

def test_defaults():
    assert config.model_id() == "distilbert-base-uncased"
    assert config.dataset_id() == "emotion"
    assert config.num_labels() == 6


def test_overrides(monkeypatch):
    monkeypatch.setenv("HF_MODEL", "bert-base-uncased")
    monkeypatch.setenv("NUM_LABELS", "3")
    assert config.model_id() == "bert-base-uncased"
    assert config.num_labels() == 3


def test_model_snapshot_precedence(monkeypatch):
    """When HF_MODEL_SNAPSHOT is set, surgery.run() loads from it instead of Hub."""
    monkeypatch.setenv("HF_MODEL", "some/model")
    monkeypatch.setenv("HF_MODEL_SNAPSHOT", "/mimer/snap")
    assert config.model_snapshot() == "/mimer/snap"
    monkeypatch.delenv("HF_MODEL_SNAPSHOT", raising=False)
    assert config.model_snapshot() is None


def test_surgery_config_path_default():
    assert config.surgery_config_path() == "configs/surgery.yaml"


# ---------- three phases each have an entry point ----------

_REPO = Path(__file__).resolve().parents[1]


def test_three_phase_scripts_exist():
    """surgery -> train -> eval, one script per phase."""
    for name in ("surgery.py", "train.py", "eval.py"):
        assert (_REPO / "scripts" / name).exists(), f"missing scripts/{name}"


def test_three_phase_sbatches_exist():
    """Each phase must have a dedicated sbatch (they have different resource profiles)."""
    for name in ("surgery.sbatch", "train.sbatch", "eval.sbatch"):
        assert (_REPO / "slurm" / name).exists(), f"missing slurm/{name}"


def test_pixi_has_task_per_phase():
    """pixi.toml must expose surgery / train / eval as named tasks."""
    pixi = (_REPO / "pixi.toml").read_text()
    for task in ("surgery", "train", "eval"):
        assert f'\n{task} ' in pixi or f"{task}=" in pixi or f"{task} =" in pixi, \
            f"pixi task '{task}' not declared"


# ---------- surgery.yaml parsing ----------

def test_surgery_yaml_shape():
    """configs/surgery.yaml must declare operation + num_labels."""
    text = (_REPO / "configs" / "surgery.yaml").read_text()
    assert "operation:" in text
    assert "num_labels:" in text
    # The shipped operation is replace_classification_head; documented in surgery.py
    assert "replace_classification_head" in text


def test_read_surgery_config_returns_dict(monkeypatch, tmp_path):
    """surgery._read_surgery_config() must load the YAML into a dict so surgery.run()
    can dispatch on its `operation` key."""
    cfg = tmp_path / "surgery.yaml"
    cfg.write_text("operation: replace_classification_head\nnum_labels: 4\nfreeze_base: true\n")
    monkeypatch.setenv("SURGERY_CONFIG", str(cfg))
    # _read_surgery_config resolves an absolute SURGERY_CONFIG path directly
    out = surgery._read_surgery_config()
    assert out["operation"] == "replace_classification_head"
    assert out["num_labels"] == 4
    assert out["freeze_base"] is True


def test_surgery_run_rejects_unknown_operation(monkeypatch, tmp_path):
    """Unknown ops must fail loudly — don't silently train on an unmodified backbone."""
    cfg = tmp_path / "surgery.yaml"
    cfg.write_text("operation: delete_everything\n")
    monkeypatch.setenv("SURGERY_CONFIG", str(cfg))
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path / "results"))
    with pytest.raises(NotImplementedError, match="delete_everything"):
        surgery.run(out_dir=tmp_path / "out")


# ---------- accelerate variants (all 4 ship for 22) ----------

def _accelerate_dir() -> Path:
    return _REPO / "configs" / "accelerate"


def test_all_four_accelerate_variants_present():
    """22 supports the single-GPU case too (a small classifier often fits on one GPU),
    in addition to the three multi-GPU strategies."""
    for variant in ("single", "ds_zero2", "ds_zero3", "fsdp"):
        assert (_accelerate_dir() / f"{variant}.yaml").exists(), f"missing {variant}.yaml"


def test_single_accelerate_config_is_non_distributed():
    """single.yaml must declare distributed_type: NO — otherwise accelerate
    will try to spawn extra workers on a one-GPU job."""
    blob = (_accelerate_dir() / "single.yaml").read_text()
    assert "distributed_type: NO" in blob
    assert "num_processes: 1" in blob


def test_pixi_train_task_honors_accelerate_config_env():
    """The `train` pixi task uses ${ACCELERATE_CONFIG:-single} — user flips
    variant with an env var, no pixi.toml edit needed."""
    pixi = (_REPO / "pixi.toml").read_text()
    assert "ACCELERATE_CONFIG" in pixi
    assert "configs/accelerate" in pixi
