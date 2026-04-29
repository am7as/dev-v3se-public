#!/usr/bin/env bash
# Read-only shared dataset from /mimer/NOBACKUP/Datasets/. Edit the bind to
# match your specific dataset.
#SBATCH --account=<PROJECT_ID>
#SBATCH --partition=alvis
#SBATCH --job-name=data-multi-shared
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err
#SBATCH --time=0-01:00:00
#SBATCH --cpus-per-task=4
#SBATCH --gpus-per-node=T4:1

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
[ -f .env ] && { set -a; . ./.env; set +a; }
export RESULTS_DIR="${RESULTS_DIR:-$PWD/results}"
mkdir -p "$RESULTS_DIR"

SIF="${SIF:-./dev.sif}"
[ -f "$SIF" ] || { echo "Missing $SIF" >&2; exit 1; }

SHARED="${SHARED_PATH:-/mimer/NOBACKUP/Datasets/ImageNet}"

apptainer run --bind .:/workspace \
    --bind "$SHARED":/data:ro \
    "$SIF" \
    pixi run process --source mimer_shared
