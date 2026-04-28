Bootstrap: docker
From: ghcr.io/prefix-dev/pixi:0.48.0-noble

%files
    pixi.toml         /workspace/pixi.toml
    pyproject.toml    /workspace/pyproject.toml
    src               /workspace/src
    scripts           /workspace/scripts
    configs           /workspace/configs
    # placeholder:adapter — script swaps this to the real adapter dir
    ADAPTER_SRC        /opt/adapter

%environment
    export PIXI_HOME=/opt/pixi
    export PATH=/opt/pixi/bin:$PATH
    export BUNDLED_ADAPTER_DIR=/opt/adapter
    export BUNDLED_BASE_DIR=/opt/base
    # placeholder:base-model — template-time literal (logical id, for info only)
    export HF_MODEL=BASE_MODEL
    # Resolve the base model from the baked-in dir; inference runs offline.
    export HF_MODEL_SNAPSHOT=/opt/base
    export HF_HUB_OFFLINE=1
    export TRANSFORMERS_OFFLINE=1

%post
    set -e
    apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl git tini python3 python3-pip && \
        rm -rf /var/lib/apt/lists/*

    cd /workspace && pixi install

    # Bake the base model into the SIF at build time.
    # BASE_MODEL and optional HF_TOKEN come from template-time substitution.
    python3 -m pip install --no-cache-dir "huggingface_hub[cli]>=0.24"
    mkdir -p /opt/base
    if [ -n "${HF_TOKEN:-}" ]; then
        huggingface-cli download BASE_MODEL \
            --local-dir /opt/base --local-dir-use-symlinks False \
            --token "${HF_TOKEN}"
    else
        huggingface-cli download BASE_MODEL \
            --local-dir /opt/base --local-dir-use-symlinks False
    fi

    # Record what was baked in.
    {
      echo "BASE_MODEL=BASE_MODEL"
      echo "BUILT_AT=$(date -u +%FT%TZ)"
    } > /opt/bundle-metadata.txt

%runscript
    cd /workspace
    # Bundled SIFs run inference by default, using the pinned adapter
    # layered on top of the pre-baked base model at /opt/base.
    exec pixi run infer --adapter-dir "$BUNDLED_ADAPTER_DIR" --base-dir "$BUNDLED_BASE_DIR" "$@"

%help
    Self-contained fine-tuned-model SIF.
    Base model: BASE_MODEL   (baked at /opt/base, loaded via HF_MODEL_SNAPSHOT)
    Adapter baked at /opt/adapter

    Built fully offline — no Hub access needed at run time.
    For gated base models, pass HF_TOKEN to the build step.

    Run:
        apptainer run --nv <this>.sif --prompt "hello"
