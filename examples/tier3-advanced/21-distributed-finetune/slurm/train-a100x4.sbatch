#!/usr/bin/env bash
# 4× A100 distributed finetune. Edit --account, time, and any .env vars.
#SBATCH --account=<PROJECT_ID>
#SBATCH --partition=alvis
#SBATCH --job-name=dist-ft-a100x4
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err
#SBATCH --time=1-00:00:00
#SBATCH --gpus-per-node=A100:4
#SBATCH --cpus-per-task=16

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
[ -f .env ] && { set -a; . ./.env; set +a; }

# Checkpoint trees + HF cache for 16–140 GB base models on 4× A100 will
# blow Cephyr's 30 GiB / 60k-file quota in seconds. Pin both to Mimer
# when running on Alvis. Laptop fallback preserves $PWD behaviour.
if [ -n "${MIMER_PROJECT_PATH:-}" ]; then
    export RESULTS_DIR="${RESULTS_DIR:-${MIMER_PROJECT_PATH}/results}"
    export HF_HOME="${HF_HOME:-${MIMER_PROJECT_PATH}/.hf-cache}"
else
    echo "WARNING: MIMER_PROJECT_PATH unset — falling back to \$PWD. On Alvis this will hit the Cephyr quota." >&2
    export RESULTS_DIR="${RESULTS_DIR:-$PWD/results}"
    export HF_HOME="${HF_HOME:-$PWD/.hf-cache}"
fi
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HF_HOME}"
mkdir -p "$RESULTS_DIR" "$HF_HOME"

SIF="${SIF:-./dev.sif}"
[ -f "$SIF" ] || { echo "Missing $SIF — build with 'apptainer build dev.sif apptainer/dev.def'" >&2; exit 1; }

# Which accelerate config — ds_zero2 (default, fast) | ds_zero3 (big models) | fsdp
CFG="${ACCELERATE_CONFIG:-ds_zero2}"

apptainer run --nv --bind .:/workspace "$SIF" \
    accelerate launch --config_file "configs/accelerate/${CFG}.yaml" scripts/train.py
