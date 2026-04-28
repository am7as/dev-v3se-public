#!/usr/bin/env bash
# Pass: sbatch --export=ALL,CKPT=/path/to/checkpoint slurm/eval.sbatch
#SBATCH --account=<PROJECT_ID>
#SBATCH --partition=alvis
#SBATCH --job-name=reco-eval
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err
#SBATCH --time=0-00:30:00
#SBATCH --gpus-per-node=T4:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
[ -f .env ] && { set -a; . ./.env; set +a; }
: "${CKPT:?Pass CKPT=/path/to/checkpoint via --export}"
SIF="${SIF:-./dev.sif}"
[ -f "$SIF" ] || { echo "Missing $SIF" >&2; exit 1; }
apptainer run --nv --bind .:/workspace "$SIF" pixi run eval --ckpt "$CKPT"
