#!/usr/bin/env bash
# Your own writable data, bound into /data. Defaults to Mimer
# (`mimer_project` allocation) — Cephyr's 30 GiB / 60k-file cap is
# too small for real datasets. Override PRIVATE_PATH to point at a
# Cephyr dir if you need that for tiny configs only.
#SBATCH --account=<PROJECT_ID>
#SBATCH --partition=alvis
#SBATCH --job-name=data-multi-private
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err
#SBATCH --time=0-01:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
[ -f .env ] && { set -a; . ./.env; set +a; }
export RESULTS_DIR="${RESULTS_DIR:-$PWD/results}"
mkdir -p "$RESULTS_DIR"

SIF="${SIF:-./dev.sif}"
[ -f "$SIF" ] || { echo "Missing $SIF" >&2; exit 1; }

# Default path follows the `mimer_project` example in configs/sources.yaml.
# `<naiss-id>` and `<cid>` are placeholders — set PRIVATE_PATH or .env to
# your real Mimer allocation before submitting.
PRIVATE="${PRIVATE_PATH:-/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-data}"

apptainer run --bind .:/workspace \
    --bind "$PRIVATE":/data \
    "$SIF" \
    pixi run process --source cephyr_private
