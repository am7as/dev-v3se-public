#!/usr/bin/env bash
#SBATCH --account=<PROJECT_ID>
#SBATCH --partition=alvis
#SBATCH --job-name=data-cephyr
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

# Common patterns — uncomment the one you need:
#
# A) Default: use the sample data shipped with the repo
# apptainer run --bind .:/workspace "$SIF" pixi run process --source sample
#
# B) Private Cephyr data
# apptainer run --bind .:/workspace \
#     --bind /cephyr/users/$USER/Alvis/my-data:/data \
#     "$SIF" pixi run process --source private
#
# C) Shared /mimer dataset (read-only)
# apptainer run --bind .:/workspace \
#     --bind /mimer/NOBACKUP/Datasets/my-shared-dataset:/data:ro \
#     "$SIF" pixi run process --source shared

apptainer run --bind .:/workspace "$SIF" pixi run process --source sample
