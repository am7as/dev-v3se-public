#!/usr/bin/env bash
# =============================================================================
# lmstudio-server.sbatch — host an LM Studio server on an Alvis GPU node.
# Writes the allocated host:port to $RESULTS_DIR so a client on the laptop
# can connect via `_shared/scripts/port-forward.sh`.
# =============================================================================

#SBATCH --account=<PROJECT_ID>
#SBATCH --partition=alvis
#SBATCH --job-name=lmstudio-server
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err
#SBATCH --time=0-04:00:00                   # 4h default — adjust to your slot
#SBATCH --gpus-per-node=T4:1                # tune T4 → A100 for bigger models
#SBATCH --cpus-per-task=4

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"

# Load the project .env if present (MIMER_GROUP_PATH etc.)
if [ -f .env ]; then
    set -a; . ./.env; set +a
fi

export DATA_DIR="${DATA_DIR:-$PWD/data}"
export RESULTS_DIR="${RESULTS_DIR:-$PWD/results}"
mkdir -p "$RESULTS_DIR"

# Model cache must be on Mimer — a 10+ GiB model would wreck Cephyr quota.
: "${MIMER_GROUP_PATH:?Set MIMER_GROUP_PATH in .env (e.g. /mimer/NOBACKUP/groups/<naiss-id>)}"
LMSTUDIO_CACHE="${LMSTUDIO_CACHE_DIR:-$MIMER_GROUP_PATH/$USER/lmstudio}"
mkdir -p "$LMSTUDIO_CACHE"

SIF="${SIF:-./lmstudio.sif}"
[ -f "$SIF" ] || { echo "Missing $SIF — run 'apptainer build lmstudio.sif apptainer/lmstudio.def'" >&2; exit 1; }

# Pick a free port (any unused TCP port).
PORT=$(( ( RANDOM % 20000 ) + 20000 ))
HOST=$(hostname -s)

# Publish host:port so the laptop client knows where to connect.
echo "$HOST" > "$RESULTS_DIR/lmstudio-host.txt"
echo "$PORT" > "$RESULTS_DIR/lmstudio-port.txt"

echo "LM Studio server: http://$HOST:$PORT  (job $SLURM_JOB_ID on $HOST)"
echo "From laptop, port-forward:"
echo "    ssh -L $PORT:$HOST:$PORT <cid>@${ALVIS_LOGIN_HOST:-alvis2.c3se.chalmers.se}"
echo "Then OPENAI_BASE_URL=http://localhost:$PORT/v1"

apptainer run --nv \
    --bind "$LMSTUDIO_CACHE":/tmp/lmstudio \
    --bind "$RESULTS_DIR":/results \
    "$SIF" \
    server start --port "$PORT" --host 0.0.0.0

# `lms server start` blocks until the allocation ends.
