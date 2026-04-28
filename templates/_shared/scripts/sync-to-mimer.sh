#!/usr/bin/env bash
# =============================================================================
# Push data / weights / results from laptop to the project's Mimer group root.
# Use sync-to-cephyr.sh for CODE; use this script for DATA / MODELS / BIG RESULTS.
#
# Reads CEPHYR_USER and MIMER_GROUP_PATH (or MIMER_PROJECT_PATH) from .env.
#
# Usage:
#     bash _shared/scripts/sync-to-mimer.sh <local-src-dir> [<remote-subdir>]
#     bash _shared/scripts/sync-to-mimer.sh ./data                    # → $MIMER_GROUP_PATH/data/
#     bash _shared/scripts/sync-to-mimer.sh ./models models/llama-8b  # → $MIMER_GROUP_PATH/models/llama-8b/
#     bash _shared/scripts/sync-to-mimer.sh --dry-run ./data
# =============================================================================

set -euo pipefail

DRY_RUN=""
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN="--dry-run"
    shift
fi

SRC="${1:-}"
SUBDIR="${2:-}"

if [ -z "$SRC" ]; then
    echo "Usage: $0 [--dry-run] <local-src-dir> [<remote-subdir>]" >&2
    exit 1
fi

if [ ! -d "$SRC" ]; then
    echo "ERROR: source '$SRC' is not a directory." >&2
    exit 1
fi

# Load .env if present (only exports lines of the form KEY=value; safe).
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    . ./.env
    set +a
fi

: "${CEPHYR_USER:?Set CEPHYR_USER in .env or pass it inline}"
: "${MIMER_GROUP_PATH:?Set MIMER_GROUP_PATH in .env, e.g. /mimer/NOBACKUP/groups/naiss2025-22-321}"
: "${CEPHYR_TRANSFER_HOST:=alvis2.c3se.chalmers.se}"

# If SUBDIR is not given, derive from basename of SRC.
if [ -z "$SUBDIR" ]; then
    SUBDIR="$(basename "$(realpath "$SRC")")"
fi

DEST="${CEPHYR_USER}@${CEPHYR_TRANSFER_HOST}:${MIMER_GROUP_PATH}/${SUBDIR}/"

echo "Syncing  $SRC/   →  $DEST"
echo "Excluded: .DS_Store, Thumbs.db, *.pyc, __pycache__/"
echo

rsync -avh --progress $DRY_RUN \
    --exclude='.DS_Store' \
    --exclude='Thumbs.db' \
    --exclude='*.pyc' \
    --exclude='__pycache__/' \
    "$SRC/" "$DEST"

echo
echo "Done. On Alvis:"
echo "    ls ${MIMER_GROUP_PATH}/${SUBDIR}"
echo "    # Bind this path into your apptainer run, e.g.:"
echo "    #     --bind ${MIMER_GROUP_PATH}/${SUBDIR}:/data"
