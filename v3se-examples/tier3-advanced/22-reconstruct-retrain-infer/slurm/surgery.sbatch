#!/usr/bin/env bash
#SBATCH --account=<PROJECT_ID>
#SBATCH --partition=alvis
#SBATCH --job-name=reco-surgery
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err
#SBATCH --time=0-00:20:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
[ -f .env ] && { set -a; . ./.env; set +a; }
export RESULTS_DIR="${RESULTS_DIR:-$PWD/results}"
export HF_HOME="${HF_HOME:-$PWD/.hf-cache}"
mkdir -p "$RESULTS_DIR" "$HF_HOME"
SIF="${SIF:-./dev.sif}"
[ -f "$SIF" ] || { echo "Missing $SIF" >&2; exit 1; }
apptainer run --bind .:/workspace "$SIF" pixi run surgery
