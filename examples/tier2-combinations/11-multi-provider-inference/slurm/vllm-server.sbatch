#!/usr/bin/env bash
# vLLM OpenAI-compatible server on Alvis. See _shared/slurm/vllm-server.sbatch
# for the full skeleton; this file is the template-specific copy.
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
[ -f .env ] && { set -a; . ./.env; set +a; }

: "${VLLM_MODEL:?Set VLLM_MODEL in .env}"
: "${VLLM_TENSOR_PARALLEL:=1}"

export VLLM_PORT="$(python3 -c 'import socket;s=socket.socket();s.bind(("",0));print(s.getsockname()[1]);s.close()')"
export RESULTS_DIR="${RESULTS_DIR:-$PWD/results}"
mkdir -p "$RESULTS_DIR"
echo "${VLLM_PORT}" > "$RESULTS_DIR/vllm-port.txt"
echo "$(hostname)" > "$RESULTS_DIR/vllm-host.txt"

export HF_HOME="${HF_HOME:-$PWD/.hf-cache}"
mkdir -p "$HF_HOME"

VLLM_SIF="${VLLM_SIF:-./vllm.sif}"
[ -f "$VLLM_SIF" ] || apptainer build "$VLLM_SIF" ../../_shared/apptainer/vllm.def

apptainer run --nv --bind .:/workspace \
    --env VLLM_MODEL="$VLLM_MODEL" \
    --env VLLM_PORT="$VLLM_PORT" \
    --env VLLM_TENSOR_PARALLEL="$VLLM_TENSOR_PARALLEL" \
    --env HF_HOME="$HF_HOME" \
    "$VLLM_SIF"
