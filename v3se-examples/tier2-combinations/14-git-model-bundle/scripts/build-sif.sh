#!/usr/bin/env bash
# =============================================================================
# Build bundle.sif with the model weights baked in.
# Reads MODEL_REPO / MODEL_REF from .env.
# Output: ./bundle.sif
# =============================================================================

set -euo pipefail

# Snapshot caller-provided overrides BEFORE sourcing .env, so a shell
# prefix (`MODEL_REPO=... bash scripts/build-sif.sh`) wins over .env.
_caller_MODEL_REPO="${MODEL_REPO:-}"
_caller_MODEL_REF="${MODEL_REF:-}"

if [ -f .env ]; then
    set -a; . ./.env; set +a
fi

# Restore caller-provided values (precedence: shell exports > .env).
[ -n "$_caller_MODEL_REPO" ] && MODEL_REPO="$_caller_MODEL_REPO"
[ -n "$_caller_MODEL_REF" ] && MODEL_REF="$_caller_MODEL_REF"

: "${MODEL_REPO:?Set MODEL_REPO in .env or pass MODEL_REPO=... before the command}"
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
echo "    scp $OUT <cid>@alvis2.c3se.chalmers.se:/mimer/NOBACKUP/groups/<naiss-id>/<cid>/sifs/"
