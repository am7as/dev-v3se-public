"""Smoke tests: verify UNIQUE behavior of 21-distributed-finetune.

This example runs a full-parameter finetune via `accelerate launch` with
one of three shipped configs (ds_zero2, ds_zero3, fsdp). The Python
training loop stays single-GPU-looking; the distribution strategy is
chosen at launch time via the ACCELERATE_CONFIG env var -> configs file.

eval.py knows how to consolidate sharded checkpoints (DeepSpeed ZeRO-3
shards, FSDP safetensors shards) back into a loadable HF tree.
"""
from __future__ import annotations

from pathlib import Path

from dist_ft import config


# ---------- config knobs ----------

def test_model_default_is_llama_8b():
    """The shipped reference target — full-param ft of 8B on 4xA100."""
    assert config.model_id() == "meta-llama/Llama-3.1-8B-Instruct"


def test_dataset_default():
    assert config.dataset_id() == "tatsu-lab/alpaca"
    assert config.dataset_split() == "train"


def test_batch_accum_and_lr_defaults():
    """Hyperparameters tuned for the shipped 8B-on-4xA100 scenario."""
    assert config.per_device_batch() == 4
    assert config.grad_accum() == 8
    assert config.learning_rate() == 2e-5
    assert config.max_seq_len() == 2048


def test_training_hyperparams_env_overrides(monkeypatch):
    monkeypatch.setenv("PER_DEVICE_BATCH", "8")
    monkeypatch.setenv("GRAD_ACCUM", "16")
    monkeypatch.setenv("MAX_SEQ_LEN", "4096")
    assert config.per_device_batch() == 8
    assert config.grad_accum() == 16
    assert config.max_seq_len() == 4096


def test_save_limits():
    """Checkpoint retention matters on Mimer (no backups, quota pressure)."""
    assert config.save_steps() == 500
    assert config.save_total_limit() == 3


# ---------- accelerate configs ----------

def _accelerate_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "configs" / "accelerate"


def test_all_three_accelerate_variants_present():
    """Three distribution strategies must ship as ready-to-use configs.
    (Single-GPU needs no accelerate config — plain `python scripts/train.py`
    works, so it is intentionally NOT shipped here.)"""
    d = _accelerate_dir()
    for variant in ("ds_zero2", "ds_zero3", "fsdp"):
        assert (d / f"{variant}.yaml").exists(), f"missing {variant}.yaml"


def test_ds_zero2_config_declares_deepspeed():
    blob = (_accelerate_dir() / "ds_zero2.yaml").read_text().lower()
    assert "deepspeed" in blob
    assert "zero_stage: 2" in blob


def test_ds_zero3_config_mentions_zero_stage_3():
    blob = (_accelerate_dir() / "ds_zero3.yaml").read_text().lower()
    # ZeRO-3 is identified by `zero_stage: 3` or a `zero3_*` flag
    assert "zero_stage: 3" in blob or "zero3" in blob


def test_fsdp_config_mentions_fsdp():
    blob = (_accelerate_dir() / "fsdp.yaml").read_text().lower()
    assert "fsdp" in blob


# ---------- slurm launch wires ACCELERATE_CONFIG ----------

def test_sbatch_reads_accelerate_config_env():
    """train-a100x4.sbatch must honor ACCELERATE_CONFIG so a user can flip
    between ds_zero2 / ds_zero3 / fsdp without editing the sbatch."""
    sbatch = (Path(__file__).resolve().parents[1] / "slurm" / "train-a100x4.sbatch")
    assert sbatch.exists()
    text = sbatch.read_text()
    assert "ACCELERATE_CONFIG" in text


# ---------- eval.py consolidates sharded checkpoints ----------

def test_eval_has_deepspeed_and_fsdp_consolidation():
    """eval.py must know about both shard shapes the three configs produce.
    Checking presence of the detection functions, not their behavior."""
    eval_py = (Path(__file__).resolve().parents[1] / "scripts" / "eval.py").read_text()
    assert "_is_deepspeed_zero" in eval_py
    assert "_is_fsdp_sharded" in eval_py
    assert "_consolidate" in eval_py
    # DeepSpeed's recovery helper
    assert "zero_to_fp32" in eval_py
    # FSDP merge path
    assert "merge-weights" in eval_py
