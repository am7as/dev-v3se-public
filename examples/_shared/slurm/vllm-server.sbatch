#!/usr/bin/env bash
# =============================================================================
# vLLM OpenAI-compatible server as a Slurm job on Alvis.
# Launches the server, writes its port to results/vllm-port.txt so client
# code can find it, and keeps running until SLURM time limit.
# =============================================================================
# Env to pass in (sbatch --export=... or put in .env and source):
#     VLLM_MODEL          e.g. google/gemma-2-9b-it
#     VLLM_TENSOR_PARALLEL (default 1; must equal --gpus-per-node number)
# =============================================================================

#SBATCH --account=<PROJECT_ID>
#SBATCH --partition=alvis
#SBATCH --job-name=vllm-server
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err
#SBATCH --time=0-08:00:00
#SBATCH --gpus-per-node=A100:1
#SBATCH --cpus-per-task=8

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"

# Load .env if present
[ -f .env ] && { set -a; . ./.env; set +a; }

: "${VLLM_MODEL:?Set VLLM_MODEL}"
: "${VLLM_TENSOR_PARALLEL:=1}"

# Find a free port (C3SE-recommended pattern)
export VLLM_PORT="$(python3 -c 'import socket; s=socket.socket(); s.bind(("", 0)); print(s.getsockname()[1]); s.close()')"
echo "vLLM will listen on port ${VLLM_PORT}"

# Write port so client jobs can discover it
mkdir -p "${RESULTS_DIR:-./results}"
echo "${VLLM_PORT}" > "${RESULTS_DIR:-./results}/vllm-port.txt"
echo "$(hostname)" > "${RESULTS_DIR:-./results}/vllm-host.txt"

export HF_HOME="${HF_HOME:-$PWD/.hf-cache}"
mkdir -p "$HF_HOME"

VLLM_SIF="${VLLM_SIF:-./vllm.sif}"
if [ ! -f "$VLLM_SIF" ]; then
    echo "Building vLLM SIF…"
    apptainer build "$VLLM_SIF" _shared/apptainer/vllm.def
fi

echo "Starting vLLM server with model=${VLLM_MODEL}, TP=${VLLM_TENSOR_PARALLEL}"
apptainer run --nv \
    --bind .:/workspace \
    --env VLLM_MODEL="${VLLM_MODEL}" \
    --env VLLM_PORT="${VLLM_PORT}" \
    --env VLLM_TENSOR_PARALLEL="${VLLM_TENSOR_PARALLEL}" \
    --env HF_HOME="${HF_HOME}" \
    "$VLLM_SIF"
