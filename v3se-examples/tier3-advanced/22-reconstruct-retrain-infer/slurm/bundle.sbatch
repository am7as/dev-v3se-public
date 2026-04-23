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
#SBATCH --mem=16G

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
: "${CKPT:?Pass CKPT=/path/to/checkpoint via --export}"

TS=$(date -u +%Y%m%dT%H%M%SZ)
OUT="$PWD/results/bundles/reco-${TS}.sif"
mkdir -p "$(dirname "$OUT")"

cat > /tmp/reco-bundle-${TS}.def <<EOF
Bootstrap: docker
From: ghcr.io/prefix-dev/pixi:0.36.0-noble

%files
    ${PWD}/pixi.toml      /workspace/pixi.toml
    ${PWD}/pyproject.toml /workspace/pyproject.toml
    ${PWD}/src            /workspace/src
    ${PWD}/scripts        /workspace/scripts
    ${PWD}/configs        /workspace/configs
    ${CKPT}               /opt/model

%environment
    export PIXI_HOME=/opt/pixi
    export PATH=/opt/pixi/bin:\$PATH
    export HF_MODEL_SNAPSHOT=/opt/model

%post
    apt-get update && apt-get install -y --no-install-recommends ca-certificates curl git tini && rm -rf /var/lib/apt/lists/*
    cd /workspace && pixi install

%runscript
    cd /workspace
    exec pixi run eval --ckpt /opt/model "\$@"
EOF

apptainer build "$OUT" /tmp/reco-bundle-${TS}.def
echo "Bundled: $OUT"
