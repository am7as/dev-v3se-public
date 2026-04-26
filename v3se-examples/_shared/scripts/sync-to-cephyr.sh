#!/usr/bin/env bash
# =============================================================================
# Push project code from laptop to Cephyr. Excludes volatile/unnecessary dirs.
#
# Reads CEPHYR_USER and CEPHYR_PROJECT_PATH from .env (or args).
# Usage:
#     bash _shared/scripts/sync-to-cephyr.sh                    (uses .env)
#     bash _shared/scripts/sync-to-cephyr.sh --dry-run
#     CEPHYR_USER=myid bash _shared/scripts/sync-to-cephyr.sh   (one-off override)
# =============================================================================

set -euo pipefail

DRY_RUN=""
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN="--dry-run"
fi

# Load .env if present (only exports lines of the form KEY=value; safe).
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    . ./.env
    set +a
fi

: "${CEPHYR_USER:?Set CEPHYR_USER in .env or pass it inline (CEPHYR_USER=myid ...)}"
: "${CEPHYR_PROJECT_PATH:?Set CEPHYR_PROJECT_PATH in .env, e.g. /cephyr/users/\$CEPHYR_USER/Alvis/my-project}"
: "${CEPHYR_TRANSFER_HOST:=alvis2.c3se.chalmers.se}"

DEST="${CEPHYR_USER}@${CEPHYR_TRANSFER_HOST}:${CEPHYR_PROJECT_PATH}/"

echo "Syncing $(pwd)/  →  $DEST"
echo "Excluded: .pixi/, .venv/, __pycache__/, .hf-cache/, results/, *.sif, .git/"
echo

rsync -avh --progress $DRY_RUN \
    --exclude='.pixi/' \
    --exclude='.venv/' \
    --exclude='__pycache__/' \
    --exclude='*.egg-info/' \
    --exclude='.pytest_cache/' \
    --exclude='.hf-cache/' \
    --exclude='results/' \
    --exclude='*.sif' \
    --exclude='.git/' \
    --exclude='.env' \
    --exclude='slurm-*.out' \
    --exclude='slurm-*.err' \
    ./ "$DEST"

echo
echo "Done. SSH to Alvis and continue:"
echo "    ssh ${CEPHYR_USER}@alvis2.c3se.chalmers.se"
echo "    cd ${CEPHYR_PROJECT_PATH}"
echo "    apptainer build dev.sif apptainer/dev.def"
echo "    sbatch slurm/gpu-t4.sbatch"
