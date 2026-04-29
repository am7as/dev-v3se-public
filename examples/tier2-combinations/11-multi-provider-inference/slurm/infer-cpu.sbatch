#!/usr/bin/env bash
# Client-side inference job. Provider is whatever DEFAULT_PROVIDER in .env
# says, unless overridden by --provider.
#SBATCH --account=<PROJECT_ID>
#SBATCH --partition=alvis
#SBATCH --job-name=infer-multi
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err
#SBATCH --time=0-00:30:00
#SBATCH --cpus-per-task=2
#SBATCH --gpus-per-node=T4:1

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
[ -f .env ] && { set -a; . ./.env; set +a; }
export RESULTS_DIR="${RESULTS_DIR:-$PWD/results}"
mkdir -p "$RESULTS_DIR"
SIF="${SIF:-./dev.sif}"
[ -f "$SIF" ] || { echo "Missing $SIF" >&2; exit 1; }

PROMPT="${PROMPT:-Write a haiku about GPUs.}"
PROVIDER="${PROVIDER:-$DEFAULT_PROVIDER}"

# For claude_cli provider, bind credentials in from Cephyr:
# CLAUDE_BINDS="--bind /cephyr/users/$USER/.claude:/root/.claude --bind /cephyr/users/$USER/.claude.json:/root/.claude.json"
CLAUDE_BINDS=""

apptainer run --bind .:/workspace $CLAUDE_BINDS "$SIF" \
    pixi run infer --provider "$PROVIDER" --prompt "$PROMPT"
