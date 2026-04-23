#!/usr/bin/env bash
# =============================================================================
# Build a Docker image with model weights baked in (laptop-only).
# Reads MODEL_REPO / MODEL_REF from .env.
# Output: docker image tagged git-model-bundle.
# =============================================================================

set -euo pipefail

if [ -f .env ]; then
    set -a; . ./.env; set +a
fi

: "${MODEL_REPO:?Set MODEL_REPO in .env (git URL of the model repo)}"
: "${MODEL_REF:=main}"
TAG="${1:-git-model-bundle}"

echo "Building docker image '$TAG' with:"
echo "  MODEL_REPO=$MODEL_REPO"
echo "  MODEL_REF=$MODEL_REF"
echo

docker build \
    --build-arg MODEL_REPO="$MODEL_REPO" \
    --build-arg MODEL_REF="$MODEL_REF" \
    -f Dockerfile.bundle -t "$TAG" .

echo
echo "Done. Run locally:"
echo "    docker run --gpus all -v \"\$PWD\":/workspace $TAG pixi run infer --prompt 'Hello'"
