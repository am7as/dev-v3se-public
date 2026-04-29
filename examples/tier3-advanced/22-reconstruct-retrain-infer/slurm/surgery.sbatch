#!/usr/bin/env bash
#SBATCH --account=<PROJECT_ID>
#SBATCH --partition=alvis
#SBATCH --job-name=reco-surgery
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err
#SBATCH --time=0-00:20:00
#SBATCH --cpus-per-task=4
#SBATCH --gpus-per-node=T4:1

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
[ -f .env ] && { set -a; . ./.env; set +a; }

# Surgery downloads the donor model + writes the surgeried checkpoint —
# 5–60 GB. Pin to Mimer; Cephyr 30 GiB cap blows immediately.
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
[ -f "$SIF" ] || { echo "Missing $SIF" >&2; exit 1; }
apptainer run --bind .:/workspace "$SIF" pixi run surgery
