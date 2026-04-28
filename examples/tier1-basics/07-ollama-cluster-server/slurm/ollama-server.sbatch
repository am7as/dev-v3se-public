#!/usr/bin/env bash
# =============================================================================
# ollama-server.sbatch — host an Ollama server on an Alvis GPU node.
# Writes the allocated host:port to $RESULTS_DIR so a client on the laptop
# can connect via `_shared/scripts/port-forward.sh`.
# =============================================================================

#SBATCH --account=<PROJECT_ID>
#SBATCH --partition=alvis
#SBATCH --job-name=ollama-server
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err
#SBATCH --time=0-04:00:00                   # 4h default
#SBATCH --gpus-per-node=T4:1                # tune T4 → A100 for bigger models
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"

if [ -f .env ]; then
    set -a; . ./.env; set +a
fi

export DATA_DIR="${DATA_DIR:-$PWD/data}"
export RESULTS_DIR="${RESULTS_DIR:-$PWD/results}"
mkdir -p "$RESULTS_DIR"

: "${MIMER_GROUP_PATH:?Set MIMER_GROUP_PATH in .env (e.g. /mimer/NOBACKUP/groups/<naiss-id>)}"
OLLAMA_CACHE="${OLLAMA_MODELS:-$MIMER_GROUP_PATH/$USER/ollama/models}"
mkdir -p "$OLLAMA_CACHE"

OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.1:8b}"

SIF="${SIF:-./ollama.sif}"
[ -f "$SIF" ] || { echo "Missing $SIF — run 'apptainer build ollama.sif apptainer/ollama.def'" >&2; exit 1; }

# Pick a free-ish port (Ollama's default is 11434; keep it unless you collide).
PORT="${OLLAMA_PORT:-11434}"
HOST=$(hostname -s)

echo "$HOST" > "$RESULTS_DIR/ollama-host.txt"
echo "$PORT" > "$RESULTS_DIR/ollama-port.txt"

echo "Ollama server: http://$HOST:$PORT  (job $SLURM_JOB_ID on $HOST)"
echo "From laptop, port-forward:"
echo "    ssh -L $PORT:$HOST:$PORT <cid>@${ALVIS_LOGIN_HOST:-alvis2.c3se.chalmers.se}"
echo "Then OPENAI_BASE_URL=http://localhost:$PORT/v1"

# Start ollama serve in the background; pull the model; then wait.
apptainer exec --nv \
    --bind "$OLLAMA_CACHE":/tmp/ollama-models \
    --env OLLAMA_MODELS=/tmp/ollama-models \
    --env OLLAMA_HOST="0.0.0.0:$PORT" \
    "$SIF" \
    bash -c "ollama serve & SERVER_PID=\$!; \
             sleep 5; \
             ollama pull $OLLAMA_MODEL; \
             echo 'Ollama ready on port $PORT with model $OLLAMA_MODEL'; \
             wait \$SERVER_PID"
