#!/usr/bin/env bash
# =============================================================================
# Single-T4 GPU job on Alvis. Ideal for smoke tests of GPU code before
# committing A100 allocation time.
# =============================================================================
# Customize: -A <project>, -t <walltime>, the apptainer run line at the end.
# =============================================================================

#SBATCH --account=<PROJECT_ID>
#SBATCH --partition=alvis
#SBATCH --job-name=gpu-t4-smoke
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err
#SBATCH --time=0-00:10:00                 # 10 minutes — T4 smoke
#SBATCH --gpus-per-node=T4:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"

export DATA_DIR="${DATA_DIR:-./data}"
export RESULTS_DIR="${RESULTS_DIR:-./results}"
export MODELS_DIR="${MODELS_DIR:-./models}"
# HuggingFace cache must NOT be in $HOME (quota). Put it next to results.
export HF_HOME="${HF_HOME:-$PWD/.hf-cache}"
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HF_HOME}"
mkdir -p "$RESULTS_DIR" "$HF_HOME"

SIF="${SIF:-./dev.sif}"
if [ ! -f "$SIF" ]; then
    echo "ERROR: $SIF not found. Run 'apptainer build dev.sif apptainer/dev.def' first." >&2
    exit 1
fi

# --nv exposes the GPU inside the container. Critical — without it torch
# reports no CUDA devices.
apptainer run --nv \
    --bind .:/workspace \
    "$SIF" \
    pixi run smoke
