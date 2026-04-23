#!/usr/bin/env bash
# =============================================================================
# Build bundle.sif with the model weights baked in.
# Reads MODEL_REPO / MODEL_REF from .env.
# Output: ./bundle.sif
# =============================================================================

set -euo pipefail

if [ -f .env ]; then
    set -a; . ./.env; set +a
fi

: "${MODEL_REPO:?Set MODEL_REPO in .env (git URL of the model repo)}"
: "${MODEL_REF:=main}"

OUT="${1:-bundle.sif}"

echo "Building $OUT with:"
echo "  MODEL_REPO=$MODEL_REPO"
echo "  MODEL_REF=$MODEL_REF"
echo

apptainer build \
    --build-arg MODEL_REPO="$MODEL_REPO" \
    --build-arg MODEL_REF="$MODEL_REF" \
    "$OUT" apptainer/bundle.def

echo
echo "Done. Run locally:"
echo "    apptainer run --nv $OUT pixi run infer --prompt 'Hello'"
echo "Or push to cluster:"
echo "    scp $OUT <cid>@vera2.c3se.chalmers.se:/mimer/NOBACKUP/groups/<naiss-id>/<cid>/sifs/"
