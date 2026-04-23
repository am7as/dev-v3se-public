#!/usr/bin/env bash
# =============================================================================
# gpu-t4.sbatch — T4 GPU inference job for 11-multi-provider-inference.
#
# Use this sbatch when the chosen provider needs a local GPU:
#   PROVIDER=vllm        — talks to a locally-running vLLM server; the
#                          server itself is launched by vllm-server.sbatch.
#                          This client sbatch just spends T4 on orchestration.
#
# For API-token and CLI-subscription flows (no GPU needed) use infer-cpu.sbatch
# instead — those waste a GPU allocation on HTTPS/subprocess work.
# =============================================================================

#SBATCH --account=<PROJECT_ID>
#SBATCH --partition=alvis
#SBATCH --job-name=multi-provider-gpu
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err
#SBATCH --time=0-00:30:00
#SBATCH --gpus-per-node=T4:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"

[ -f .env ] && { set -a; . ./.env; set +a; }

export RESULTS_DIR="${RESULTS_DIR:-$PWD/results}"
mkdir -p "$RESULTS_DIR"

SIF="${SIF:-./dev.sif}"
[ -f "$SIF" ] || { echo "Missing $SIF — run 'apptainer build dev.sif apptainer/dev.def' first" >&2; exit 1; }

PROMPT="${PROMPT:-What is the capital of France?}"
PROVIDER="${PROVIDER:-vllm}"

# --nv exposes GPUs; the vLLM client needs CUDA to tokenise efficiently.
apptainer run --nv \
    --bind .:/workspace \
    "$SIF" \
    pixi run infer --provider "$PROVIDER" --prompt "$PROMPT"
