#!/usr/bin/env bash
# =============================================================================
# Forward a port from an Alvis compute node to your laptop.
# Usage:
#     bash _shared/scripts/port-forward.sh <jobid> [container_port] [local_port]
# Example:
#     bash _shared/scripts/port-forward.sh 123456 8888 8890
# then open http://localhost:8890 in your browser.
# =============================================================================

set -euo pipefail

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <jobid> [container_port=8888] [local_port=8890]" >&2
    exit 1
fi

JOBID="$1"
CONTAINER_PORT="${2:-8888}"
LOCAL_PORT="${3:-8890}"

# Load .env if present
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    . ./.env
    set +a
fi

: "${CEPHYR_USER:?Set CEPHYR_USER in .env}"
: "${ALVIS_LOGIN_HOST:=alvis2.c3se.chalmers.se}"

# Look up which compute node Slurm assigned the job.
NODE=$(ssh "${CEPHYR_USER}@${ALVIS_LOGIN_HOST}" \
    "squeue -j ${JOBID} -h -o '%N'" | tr -d ' ')

if [ -z "$NODE" ]; then
    echo "ERROR: could not find node for job ${JOBID}. Is it running?" >&2
    ssh "${CEPHYR_USER}@${ALVIS_LOGIN_HOST}" "squeue -u \$USER" >&2
    exit 2
fi

echo "Job ${JOBID} is on compute node: ${NODE}"
echo "Forwarding laptop :${LOCAL_PORT}  →  ${NODE}:${CONTAINER_PORT}"
echo "Open http://localhost:${LOCAL_PORT}/ when ready. Ctrl-C to stop the tunnel."
echo

exec ssh -N -L "${LOCAL_PORT}:${NODE}:${CONTAINER_PORT}" \
    "${CEPHYR_USER}@${ALVIS_LOGIN_HOST}"
