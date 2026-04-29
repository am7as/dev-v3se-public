#!/usr/bin/env bash
# Bundle a trained adapter into a deployable SIF. Needs login node or
# compute node with fakeroot/user-namespaces for apptainer build.
# Pass: sbatch --export=ALL,ADAPTER=/cephyr/.../adapters/<ts> slurm/bundle.sbatch
#SBATCH --account=<PROJECT_ID>
#SBATCH --partition=alvis
#SBATCH --job-name=train-infer-bundle
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err
#SBATCH --time=0-01:00:00
#SBATCH --cpus-per-task=4
#SBATCH --gpus-per-node=T4:1

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
[ -f .env ] && { set -a; . ./.env; set +a; }
: "${ADAPTER:?Pass ADAPTER=/path/to/adapter via --export}"
export RESULTS_DIR="${RESULTS_DIR:-$PWD/results}"
mkdir -p "$RESULTS_DIR/bundles"

SIF="${SIF:-./dev.sif}"
[ -f "$SIF" ] || { echo "Missing $SIF" >&2; exit 1; }

apptainer run --bind .:/workspace "$SIF" pixi run bundle --adapter-dir "$ADAPTER"
