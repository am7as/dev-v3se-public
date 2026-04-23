#!/usr/bin/env bash
# =============================================================================
# Download a HuggingFace model and bake it into a single SIF file.
# Respects the 30 GiB / 60k file cluster quota — unpacked weights go to a
# tmpdir that's cleaned up; only the SIF remains on Cephyr.
#
# Usage:
#     bash _shared/scripts/fetch-hf-model.sh <org/name> <output.sif> [<hf_token>]
# Example:
#     bash _shared/scripts/fetch-hf-model.sh meta-llama/Llama-3.1-8B llama3-8b.sif
# =============================================================================

set -euo pipefail

if [ "$#" -lt 2 ]; then
    echo "Usage: $0 <org/name> <output.sif> [<hf_token>]" >&2
    exit 1
fi

MODEL="$1"
OUT_SIF="$2"
HF_TOKEN="${3:-${HF_TOKEN:-}}"

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

echo "Downloading ${MODEL} to ${TMPDIR} …"
export HF_HOME="${TMPDIR}/hf"
mkdir -p "$HF_HOME"

if command -v huggingface-cli >/dev/null 2>&1; then
    if [ -n "$HF_TOKEN" ]; then
        huggingface-cli download "$MODEL" --token "$HF_TOKEN" --local-dir "${TMPDIR}/model"
    else
        huggingface-cli download "$MODEL" --local-dir "${TMPDIR}/model"
    fi
else
    echo "ERROR: huggingface-cli not found. Install with: pip install huggingface_hub[cli]" >&2
    exit 2
fi

DEF="${TMPDIR}/model.def"
cat >"$DEF" <<EOF
Bootstrap: docker
From: ubuntu:24.04

%files
    ${TMPDIR}/model /opt/model

%environment
    export HF_MODEL_PATH=/opt/model

%runscript
    echo "This SIF embeds ${MODEL}. Bind it into your dev container:"
    echo "  apptainer run --bind /opt/model:/models/the-model <dev.sif> pixi run infer"
EOF

echo "Building SIF at ${OUT_SIF} …"
apptainer build "$OUT_SIF" "$DEF"

echo "Done. Result:"
ls -lh "$OUT_SIF"
