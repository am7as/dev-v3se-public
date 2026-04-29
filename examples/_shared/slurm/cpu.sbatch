#!/usr/bin/env bash
# =============================================================================
# CPU-only Slurm job on Alvis. Use this for data prep, scripts that don't
# touch a GPU, and smoke tests of your container itself.
# =============================================================================
# Customize: -A <project>, -t <walltime>, the apptainer run line at the end.
# =============================================================================

#SBATCH --account=<PROJECT_ID>           # e.g. NAISS2024-5-123
#SBATCH --partition=alvis
#SBATCH --job-name=cpu-job
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err
#SBATCH --time=0-00:30:00                 # 30 minutes
#SBATCH --cpus-per-task=4
#SBATCH --gpus-per-node=T4:1

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"

# Tell the template where to find its pieces (matches .env defaults).
export DATA_DIR="${DATA_DIR:-./data}"
export RESULTS_DIR="${RESULTS_DIR:-./results}"
export MODELS_DIR="${MODELS_DIR:-./models}"
mkdir -p "$RESULTS_DIR"

SIF="${SIF:-./dev.sif}"
if [ ! -f "$SIF" ]; then
    echo "ERROR: $SIF not found. Run 'apptainer build dev.sif apptainer/dev.def' first." >&2
    exit 1
fi

# Apptainer auto-binds $HOME, cwd, /cephyr, /mimer, /apps — no --bind needed.
# DEV mode: bind current dir explicitly to /workspace so the container sees
# your live code. For deployment SIFs remove --bind .:/workspace.
apptainer run \
    --bind .:/workspace \
    "$SIF" \
    pixi run smoke
