#!/usr/bin/env bash
# Pass: sbatch --export=ALL,MODEL=/path/to/surgeried/model slurm/train.sbatch
#SBATCH --account=<PROJECT_ID>
#SBATCH --partition=alvis
#SBATCH --job-name=reco-train
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err
#SBATCH --time=0-04:00:00
#SBATCH --gpus-per-node=T4:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
[ -f .env ] && { set -a; . ./.env; set +a; }
: "${MODEL:?Pass MODEL=/path/to/surgeried/model via --export}"
export RESULTS_DIR="${RESULTS_DIR:-$PWD/results}"
export HF_HOME="${HF_HOME:-$PWD/.hf-cache}"
mkdir -p "$RESULTS_DIR" "$HF_HOME"
SIF="${SIF:-./dev.sif}"
[ -f "$SIF" ] || { echo "Missing $SIF" >&2; exit 1; }

apptainer run --nv --bind .:/workspace "$SIF" \
    accelerate launch --config_file configs/accelerate/${ACCELERATE_CONFIG:-single}.yaml scripts/train.py --model "$MODEL"
