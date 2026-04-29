#!/usr/bin/env bash
# =============================================================================
# foundation — CPU smoke on Alvis
# Runs `pixi run smoke` inside the dev SIF on a CPU-only allocation. No GPU.
# =============================================================================

#SBATCH --account=<PROJECT_ID>
#SBATCH --partition=alvis
#SBATCH --job-name=foundation-cpu-smoke
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err
#SBATCH --time=0-00:05:00
#SBATCH --cpus-per-task=2
#SBATCH --gpus-per-node=T4:1

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"

export DATA_DIR="${DATA_DIR:-$PWD/data}"
export RESULTS_DIR="${RESULTS_DIR:-$PWD/results}"
export MODELS_DIR="${MODELS_DIR:-$PWD/models}"
mkdir -p "$DATA_DIR" "$RESULTS_DIR" "$MODELS_DIR"

SIF="${SIF:-./dev.sif}"
[ -f "$SIF" ] || { echo "Missing $SIF — run 'apptainer build dev.sif apptainer/dev.def' first" >&2; exit 1; }

apptainer run \
    --bind .:/workspace \
    --bind "$DATA_DIR":/data \
    --bind "$RESULTS_DIR":/results \
    --bind "$MODELS_DIR":/models \
    "$SIF" \
    pixi run smoke
