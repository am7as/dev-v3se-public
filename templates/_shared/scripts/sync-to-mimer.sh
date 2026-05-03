#!/usr/bin/env bash
# =============================================================================
# Push data / weights / results from laptop to your Mimer dir.
# Use sync-to-cephyr.sh for CODE; this script for DATA / MODELS / BIG RESULTS.
#
# Reads identity primitives from .env (CEPHYR_USER, NAISS_PROJECT_ID).
# Composes the destination path from the new C3SE convention:
#     ${MIMER_GROUP_ROOT}/users/${CEPHYR_USER}/${SUBDIR}    (default — your space)
#     ${MIMER_GROUP_ROOT}/shared/${SUBDIR}                  (with --shared)
#     ${MIMER_GROUP_ROOT}/projects/${PROJECT_NAME}/${SUBDIR} (with --project)
#
# Usage:
#     bash _shared/scripts/sync-to-mimer.sh ./data                   # → users/<cid>/data/
#     bash _shared/scripts/sync-to-mimer.sh ./models models/llama-8b # → users/<cid>/models/llama-8b/
#     bash _shared/scripts/sync-to-mimer.sh --shared ./datasets ds   # → shared/ds/
#     bash _shared/scripts/sync-to-mimer.sh --project ./outputs out  # → projects/<name>/out/
#     bash _shared/scripts/sync-to-mimer.sh --dry-run ./data
# =============================================================================

set -euo pipefail

DRY_RUN=""
SCOPE="user"  # user | shared | project

while [[ "${1:-}" == --* ]]; do
    case "$1" in
        --dry-run) DRY_RUN="--dry-run"; shift ;;
        --shared)  SCOPE="shared";   shift ;;
        --project) SCOPE="project";  shift ;;
        *) echo "Unknown flag: $1" >&2; exit 1 ;;
    esac
done

SRC="${1:-}"
SUBDIR="${2:-}"

if [ -z "$SRC" ]; then
    echo "Usage: $0 [--dry-run] [--shared|--project] <local-src-dir> [<remote-subdir>]" >&2
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

: "${CEPHYR_USER:?Set CEPHYR_USER in .env}"
: "${NAISS_PROJECT_ID:?Set NAISS_PROJECT_ID in .env, e.g. <naiss-id>}"
: "${CEPHYR_TRANSFER_HOST:=alvis2.c3se.chalmers.se}"

MIMER_GROUP_ROOT="${MIMER_GROUP_ROOT:-/mimer/NOBACKUP/groups/${NAISS_PROJECT_ID}}"

case "$SCOPE" in
    user)    REMOTE_BASE="${MIMER_GROUP_ROOT}/users/${CEPHYR_USER}" ;;
    shared)  REMOTE_BASE="${MIMER_GROUP_ROOT}/shared" ;;
    project) : "${PROJECT_NAME:?Set PROJECT_NAME in .env to use --project scope}"
             REMOTE_BASE="${MIMER_GROUP_ROOT}/projects/${PROJECT_NAME}" ;;
esac

# If SUBDIR is not given, derive from basename of SRC.
if [ -z "$SUBDIR" ]; then
    SUBDIR="$(basename "$(realpath "$SRC")")"
fi

DEST="${CEPHYR_USER}@${CEPHYR_TRANSFER_HOST}:${REMOTE_BASE}/${SUBDIR}/"

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
echo "    ls ${REMOTE_BASE}/${SUBDIR}"
echo "    # Bind this path into your apptainer run, e.g.:"
echo "    #     --bind ${REMOTE_BASE}/${SUBDIR}:/data"
