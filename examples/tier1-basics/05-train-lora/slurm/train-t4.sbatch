#!/usr/bin/env bash
#SBATCH --account=<PROJECT_ID>
#SBATCH --partition=alvis
#SBATCH --job-name=train-lora
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err
#SBATCH --time=0-01:00:00
#SBATCH --gpus-per-node=T4:1
#SBATCH --cpus-per-task=4

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"

[ -f .env ] && { set -a; . ./.env; set +a; }

# HF cache + results MUST land on Mimer when running on the cluster —
# Cephyr's 30 GiB / 60,000 file quota cannot hold LoRA cache + adapters.
# Fall back to $PWD ONLY for laptop runs where Mimer doesn't exist.
if [ -n "${MIMER_USER_DIR:-}" ]; then
    export HF_HOME="${HF_HOME:-${MIMER_USER_DIR}/.hf-cache}"
    export RESULTS_DIR="${RESULTS_DIR:-${MIMER_USER_DIR}/results}"
else
    echo "WARNING: MIMER_USER_DIR unset — set NAISS_PROJECT_ID + CEPHYR_USER in .env. Falling back to \$PWD; on Alvis this will hit the Cephyr 60k-file quota." >&2
    export HF_HOME="${HF_HOME:-$PWD/.hf-cache}"
    export RESULTS_DIR="${RESULTS_DIR:-$PWD/results}"
fi
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HF_HOME}"
mkdir -p "$RESULTS_DIR" "$HF_HOME"

SIF="${SIF:-./dev.sif}"
[ -f "$SIF" ] || { echo "Missing $SIF" >&2; exit 1; }

apptainer run --nv --bind .:/workspace "$SIF" pixi run train
