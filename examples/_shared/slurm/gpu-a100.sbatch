#!/usr/bin/env bash
# =============================================================================
# 1× A100 GPU job on Alvis. For real work (training, inference at scale).
# Test with gpu-t4.sbatch FIRST before spending A100 hours.
# =============================================================================

#SBATCH --account=<PROJECT_ID>
#SBATCH --partition=alvis
#SBATCH --job-name=gpu-a100
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err
#SBATCH --time=0-04:00:00
#SBATCH --gpus-per-node=A100:1
#SBATCH --cpus-per-task=8

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"

export DATA_DIR="${DATA_DIR:-$PWD/data}"
export RESULTS_DIR="${RESULTS_DIR:-$PWD/results}"
export MODELS_DIR="${MODELS_DIR:-$PWD/models}"
export HF_HOME="${HF_HOME:-$PWD/.hf-cache}"
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HF_HOME}"
mkdir -p "$RESULTS_DIR" "$HF_HOME"

SIF="${SIF:-./dev.sif}"
[ -f "$SIF" ] || { echo "Missing $SIF" >&2; exit 1; }

apptainer run --nv --bind .:/workspace "$SIF" "${CMD:-pixi run smoke}"
