#!/usr/bin/env bash
# =============================================================================
# Ollama client — CPU-only job on Alvis.
# API calls are network-bound, not compute-bound. No GPU needed.
# =============================================================================

#SBATCH --account=<PROJECT_ID>
#SBATCH --partition=alvis
#SBATCH --job-name=ollama-client
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err
#SBATCH --time=0-00:30:00
#SBATCH --cpus-per-task=2
#SBATCH --gpus-per-node=T4:1

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"

[ -f .env ] && { set -a; . ./.env; set +a; }

export RESULTS_DIR="${RESULTS_DIR:-$PWD/results}"
mkdir -p "$RESULTS_DIR"

SIF="${SIF:-./dev.sif}"
[ -f "$SIF" ] || { echo "Missing $SIF — run 'apptainer build dev.sif apptainer/dev.def'" >&2; exit 1; }

PROMPT="${PROMPT:-What is the capital of France?}"

apptainer run --bind .:/workspace "$SIF" pixi run infer --prompt "$PROMPT"
