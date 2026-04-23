#!/usr/bin/env bash
# =============================================================================
# Pull results back from Cephyr. Mirror of sync-to-cephyr.sh.
#
# Usage:
#     bash _shared/scripts/sync-from-cephyr.sh                (results/ only)
#     bash _shared/scripts/sync-from-cephyr.sh --full         (everything)
# =============================================================================

set -euo pipefail

MODE="results"
if [[ "${1:-}" == "--full" ]]; then
    MODE="full"
fi

[ -f .env ] && { set -a; . ./.env; set +a; }

: "${CEPHYR_USER:?Set CEPHYR_USER in .env}"
: "${CEPHYR_PROJECT_PATH:?Set CEPHYR_PROJECT_PATH in .env}"
: "${CEPHYR_TRANSFER_HOST:=vera2.c3se.chalmers.se}"

SRC="${CEPHYR_USER}@${CEPHYR_TRANSFER_HOST}:${CEPHYR_PROJECT_PATH}"

if [ "$MODE" = "results" ]; then
    echo "Pulling results from $SRC/results/"
    rsync -avh --progress "$SRC/results/" ./results/
else
    echo "Full pull from $SRC/ (code + results + slurm logs)"
    rsync -avh --progress \
        --exclude='.pixi/' --exclude='*.sif' --exclude='.hf-cache/' \
        "$SRC/" ./
fi
