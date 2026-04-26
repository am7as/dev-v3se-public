Bootstrap: docker
From: ghcr.io/prefix-dev/pixi:0.48.0-noble

%files
    # placeholder:workspace-path — sbatch substitutes the host repo root
    __WORKSPACE_PATH__/pixi.toml      /workspace/pixi.toml
    __WORKSPACE_PATH__/pyproject.toml /workspace/pyproject.toml
    __WORKSPACE_PATH__/src            /workspace/src
    __WORKSPACE_PATH__/scripts        /workspace/scripts
    __WORKSPACE_PATH__/configs        /workspace/configs
    # placeholder:ckpt-path — sbatch substitutes the surgeried/retrained ckpt dir
    __CKPT_PATH__                     /opt/model

%environment
    export PIXI_HOME=/opt/pixi
    export PATH=/opt/pixi/bin:$PATH
    export HF_MODEL_SNAPSHOT=/opt/model
    export HF_HUB_OFFLINE=1
    export TRANSFORMERS_OFFLINE=1

%post
    set -e
    apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl git tini && \
        rm -rf /var/lib/apt/lists/*
    cd /workspace && pixi install

    {
      echo "BUILT_AT=$(date -u +%FT%TZ)"
      echo "CKPT_HOST=__CKPT_PATH__"
    } > /opt/bundle-metadata.txt

%runscript
    cd /workspace
    exec pixi run eval --ckpt /opt/model "$@"

%help
    Self-contained reconstruction-retrain SIF.
    Surgeried + retrained checkpoint baked at /opt/model
    (loaded via HF_MODEL_SNAPSHOT). Runs fully offline.
    Run:
        apptainer run --nv <this>.sif --prompt "hello"
