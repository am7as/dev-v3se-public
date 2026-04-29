#!/usr/bin/env bash
# Run inference directly against a bundled SIF. No dev.sif needed — the
# bundle is self-contained.
# Pass: sbatch --export=ALL,BUNDLE=/cephyr/.../bundles/<ts>.sif,PROMPT="..." slurm/infer.sbatch
#SBATCH --account=<PROJECT_ID>
#SBATCH --partition=alvis
#SBATCH --job-name=train-infer-infer
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err
#SBATCH --time=0-00:30:00
#SBATCH --gpus-per-node=T4:1
#SBATCH --cpus-per-task=4

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
: "${BUNDLE:?Pass BUNDLE=/path/to/bundle.sif via --export}"
[ -f "$BUNDLE" ] || { echo "Bundle SIF not found: $BUNDLE" >&2; exit 1; }

PROMPT="${PROMPT:-Hello, world.}"

apptainer run --nv "$BUNDLE" --prompt "$PROMPT"
