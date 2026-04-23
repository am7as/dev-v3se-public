# `14-git-model-bundle` — model weights from a git repo, bundled into SIF or Docker image

Use when the model you want is distributed **as a git repo** (custom
architectures, research drops, proprietary internal mirrors) rather
than via HuggingFace Hub.

The pattern:

- **Cluster path**: `git clone` inside an Apptainer `%post` block →
  build artefact is a single SIF with weights baked in. One file on
  Cephyr, zero Hub dependencies.
- **Laptop path**: same clone inside a Dockerfile → Docker image
  with weights baked in. Reproducible local runs.

Both images expose the same Python entrypoint (`pixi run infer`).

## Layout diffs vs 03-hf-shared-hub

- `apptainer/bundle.def` — `%post` clones the model repo and runs
  deps install; SIF is self-contained.
- `Dockerfile.bundle` — same idea, Docker-side; built by
  `scripts/build-docker.sh`.
- `scripts/build-sif.sh` — laptop-side wrapper: `apptainer build
  bundle.sif apptainer/bundle.def`.
- `scripts/build-docker.sh` — laptop-side wrapper:
  `docker build -f Dockerfile.bundle -t <project>-bundle .`.
- `src/infer_git_model/loader.py` — loads from the baked-in path
  (`/opt/model`) rather than HF Hub.
- `.env.example` adds `MODEL_REPO` (git URL), `MODEL_REF` (branch /
  tag / commit).

## Quickstart

### Build the SIF (runs on both laptop and cluster)

**PowerShell:**

```powershell
# 1. Set the git URL of the model repo in .env.
Copy-Item .env.example .env
# Edit .env: MODEL_REPO=https://github.com/<org>/<model-repo>.git

# 2. Build the SIF — takes minutes (clone + deps + bake)
bash scripts/build-sif.sh
```

**bash / zsh:**

```bash
cp .env.example .env
# Edit .env: MODEL_REPO=https://github.com/<org>/<model-repo>.git
bash scripts/build-sif.sh
```

### Build a Docker image (laptop only)

**PowerShell:**

```powershell
bash scripts/build-docker.sh
docker run --gpus all -v ${PWD}:/workspace <project>-bundle pixi run infer --prompt "Hello"
```

**bash / zsh:**

```bash
bash scripts/build-docker.sh
docker run --gpus all -v "$PWD":/workspace <project>-bundle pixi run infer --prompt "Hello"
```

### Use the SIF on Alvis

```bash
# If built on laptop, rsync the single .sif file:
scp bundle.sif <cid>@vera2.c3se.chalmers.se:/mimer/NOBACKUP/groups/<naiss-id>/<cid>/sifs/

ssh <cid>@alvis2.c3se.chalmers.se
cd /cephyr/users/<cid>/Alvis/14-git-model-bundle
sbatch slurm/gpu-t4.sbatch                 # runs bundle.sif with pixi run infer
```

## Storage discipline

- **Build the SIF once on a login node (preferred) or on laptop** —
  don't rebuild per job.
- **Put large SIFs on Mimer**, not Cephyr:
  `/mimer/NOBACKUP/groups/<naiss-id>/<cid>/sifs/bundle.sif`.
- **Never** clone model weights into `/cephyr/users/` directly —
  they're often 10+ GiB in thousands of files (git LFS).

## When to leave

- The model IS on HF Hub → `03-hf-shared-hub` is simpler.
- You want a routable, high-throughput server →
  `11-multi-provider-inference` + vLLM.
- You want the convenience of LM Studio / Ollama catalogs →
  `06-lmstudio-cluster-server` / `07-ollama-cluster-server`.
