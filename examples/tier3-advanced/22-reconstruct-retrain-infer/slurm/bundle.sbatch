#!/usr/bin/env bash
# Package a trained checkpoint into a standalone SIF for deployment.
# Pass: sbatch --export=ALL,CKPT=/path/to/checkpoint slurm/bundle.sbatch
#SBATCH --account=<PROJECT_ID>
#SBATCH --partition=alvis
#SBATCH --job-name=reco-bundle
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err
#SBATCH --time=0-00:30:00
#SBATCH --cpus-per-task=4
#SBATCH --gpus-per-node=T4:1

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
[ -f .env ] && { set -a; . ./.env; set +a; }
: "${CKPT:?Pass CKPT=/path/to/checkpoint via --export}"

# SIF bundles bake the full base + adapter weights — easily 20–100 GB.
# Land them on Mimer; Cephyr's 30 GiB cap can't hold even one bundle.
if [ -n "${MIMER_PROJECT_PATH:-}" ]; then
    BUNDLE_DIR="${BUNDLE_DIR:-${MIMER_PROJECT_PATH}/results/bundles}"
else
    echo "WARNING: MIMER_PROJECT_PATH unset — falling back to \$PWD/results/bundles. On Alvis this will hit the Cephyr quota." >&2
    BUNDLE_DIR="${BUNDLE_DIR:-$PWD/results/bundles}"
fi
mkdir -p "$BUNDLE_DIR"

TPL="apptainer/bundle.def.tpl"
[ -f "$TPL" ] || { echo "Missing $TPL" >&2; exit 1; }

TS=$(date -u +%Y%m%dT%H%M%SZ)
OUT="$BUNDLE_DIR/reco-${TS}.sif"
DEF="$BUNDLE_DIR/reco-${TS}.def"

# Render the .def from the template, substituting host paths. `|` as the
# sed delimiter is safe for filesystem paths (which never contain `|`).
sed -e "s|__WORKSPACE_PATH__|${PWD}|g" \
    -e "s|__CKPT_PATH__|${CKPT}|g" \
    "$TPL" > "$DEF"

apptainer build "$OUT" "$DEF"
echo "Bundled: $OUT"
echo "Def kept at: $DEF"
