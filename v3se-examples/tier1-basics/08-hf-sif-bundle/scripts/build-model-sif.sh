#!/usr/bin/env bash
# =============================================================================
# Build model.sif with a HuggingFace model's weights baked in.
# Reads HF_MODEL (required) and HF_TOKEN (optional) from .env.
# Output: ./model.sif
#
# Run on laptop (Linux / WSL2 / macOS Apptainer) or on Alvis login node.
# =============================================================================

set -euo pipefail

if [ -f .env ]; then
    set -a; . ./.env; set +a
fi

: "${HF_MODEL:?Set HF_MODEL in .env (e.g. google/gemma-2-2b-it)}"
OUT="${1:-model.sif}"

echo "Building $OUT with:"
echo "  HF_MODEL=$HF_MODEL"
echo "  HF_TOKEN=$( [ -n "${HF_TOKEN:-}" ] && echo "(set)" || echo "(unset)" )"
echo

ARGS=(--build-arg "HF_MODEL=$HF_MODEL")
if [ -n "${HF_TOKEN:-}" ]; then
    ARGS+=(--build-arg "HF_TOKEN=$HF_TOKEN")
fi

apptainer build "${ARGS[@]}" "$OUT" apptainer/model.def

echo
echo "Done. $(du -h "$OUT" | cut -f1)"
echo "Run locally:"
echo "    apptainer run --nv $OUT \"Hello world\""
echo "Transfer to cluster:"
echo "    scp $OUT <cid>@vera2.c3se.chalmers.se:/mimer/NOBACKUP/groups/<naiss-id>/<cid>/sifs/"
