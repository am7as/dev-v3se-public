#!/usr/bin/env bash
# =============================================================================
# foundation — 1× T4 GPU smoke on Alvis
# Proves the SIF + --nv + GPU visibility plumbing before you start doing
# anything that needs actual compute.
# =============================================================================

#SBATCH --account=<PROJECT_ID>
#SBATCH --partition=alvis
#SBATCH --job-name=foundation-gpu-smoke
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err
#SBATCH --time=0-00:10:00
#SBATCH --gpus-per-node=T4:1
#SBATCH --cpus-per-task=4

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"

export DATA_DIR="${DATA_DIR:-$PWD/data}"
export RESULTS_DIR="${RESULTS_DIR:-$PWD/results}"
export MODELS_DIR="${MODELS_DIR:-$PWD/models}"
export HF_HOME="${HF_HOME:-$PWD/.hf-cache}"
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HF_HOME}"
mkdir -p "$DATA_DIR" "$RESULTS_DIR" "$MODELS_DIR" "$HF_HOME"

SIF="${SIF:-./dev.sif}"
[ -f "$SIF" ] || { echo "Missing $SIF — run 'apptainer build dev.sif apptainer/dev.def' first" >&2; exit 1; }

# --nv exposes GPUs to the container. Without it, nvidia-smi fails and
# torch.cuda.is_available() returns False.
apptainer run --nv \
    --bind .:/workspace \
    --bind "$DATA_DIR":/data \
    --bind "$RESULTS_DIR":/results \
    --bind "$MODELS_DIR":/models \
    "$SIF" \
    pixi run smoke
