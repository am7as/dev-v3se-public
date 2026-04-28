#!/usr/bin/env bash
#SBATCH --account=<PROJECT_ID>
#SBATCH --partition=alvis
#SBATCH --job-name=hf-hub-streaming-gpu
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err
#SBATCH --time=0-00:30:00
#SBATCH --gpus-per-node=T4:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"

[ -f .env ] && { set -a; . ./.env; set +a; }

export RESULTS_DIR="${RESULTS_DIR:-$PWD/results}"
export HF_HOME="${HF_HOME:-$PWD/.hf-cache}"
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HF_HOME}"
mkdir -p "$RESULTS_DIR" "$HF_HOME"

SIF="${SIF:-./dev.sif}"
[ -f "$SIF" ] || { echo "Missing $SIF" >&2; exit 1; }

PROMPT="${PROMPT:-Once upon a time}"

# --bind the pre-downloaded HF hub cache if HF_MODEL_SNAPSHOT is not set but
# you want to use /mimer. Adjust per your project.
apptainer run --nv \
    --bind .:/workspace \
    "$SIF" \
    pixi run infer --prompt "$PROMPT"
