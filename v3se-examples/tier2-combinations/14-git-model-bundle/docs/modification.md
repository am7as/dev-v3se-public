# Modification — `14-git-model-bundle`

Everything you might realistically need to change when adapting this
template to a real project. `usage.md` covers the first walkthrough;
this file is the follow-up edit list.

## 1. Rename the Python package

The package ships as `infer_git_model`. Rename in three places:

1. Folder: `src/infer_git_model/` → `src/<your_pkg>/`.
2. `pyproject.toml`:

   ```toml
   [tool.hatch.build.targets.wheel]
   packages = ["src/<your_pkg>"]
   ```
3. `pixi.toml` — `[workspace]` name and any script references.
4. Import sites: `scripts/infer.py`, `scripts/smoke.py`,
   `scripts/info.py`, `tests/test_smoke.py`,
   `apptainer/bundle.def`'s `%runscript` (`python3 -m infer_git_model`).

Then:

**PowerShell:**

```powershell
docker compose exec dev pixi install --force
```

**bash / zsh:**

```bash
docker compose exec dev pixi install --force
```

## 2. Set the Slurm account

Every `slurm/*.sbatch` ships with a placeholder:

```diff
-#SBATCH --account=<PROJECT_ID>
+#SBATCH --account=<your-naiss-id>
```

Do this in every file under `slurm/` — currently just
`slurm/gpu-t4.sbatch`, but any sbatch you add needs the same edit.

## 3. Swap `MODEL_REPO` / `MODEL_REF`

Single-block change in `.env`:

```ini
MODEL_REPO=git@github.com:<org>/<repo>.git      # or https://...
MODEL_REF=v2.1                                  # or a commit SHA
```

**Always** test the clone before rebuilding the SIF:

```bash
git ls-remote $MODEL_REPO | grep -E "refs/(heads|tags)/$MODEL_REF"
```

Then rebuild:

```bash
bash scripts/build-sif.sh
# or on laptop: bash scripts/build-docker.sh
```

`scripts/build-sif.sh` and `scripts/build-docker.sh` both forward
`MODEL_REPO` / `MODEL_REF` as build args, which Apptainer /
Dockerfile pick up in their `%arguments` / `ARG` stanzas.

## 4. Gated HF weights pulled during the build

Some research repos fetch a base checkpoint from HuggingFace in
their `setup.py` / `requirements.txt`. For gated base checkpoints:

```ini
# .env
HF_TOKEN=hf_xxxxxxxx
```

Then extend `apptainer/bundle.def`'s `%post` to export it:

```diff
 %post
     set -e
     apt-get update
     apt-get install -y --no-install-recommends \
         git git-lfs curl ca-certificates python3 python3-pip python3-venv
     git lfs install
+    # Authenticated HF download during `pip install .`
+    export HUGGING_FACE_HUB_TOKEN="${HF_TOKEN:-}"
```

And pass it as a build arg in `scripts/build-sif.sh`:

```diff
 apptainer build \
     --build-arg MODEL_REPO="$MODEL_REPO" \
     --build-arg MODEL_REF="$MODEL_REF" \
+    --build-arg HF_TOKEN="$HF_TOKEN" \
     "$OUT" apptainer/bundle.def
```

Remember to add `HF_TOKEN` to `%arguments` as well.

## 5. Customise the install step

Default `%post` handles two common layouts:

```bash
if [ -f requirements.txt ]; then
    python3 -m pip install --no-cache-dir -r requirements.txt
elif [ -f pyproject.toml ]; then
    python3 -m pip install --no-cache-dir .
fi
```

Change this when the repo deviates — e.g. conda-first setup, Makefile
build, `cmake` extensions:

```diff
-if [ -f requirements.txt ]; then
-    python3 -m pip install --no-cache-dir -r requirements.txt
+if [ -f environment.yml ]; then
+    curl -L https://micro.mamba.pm/api/micromamba/linux-64/latest \
+        | tar -xvj bin/micromamba
+    ./bin/micromamba create -y -n app -f environment.yml
```

Mirror the same change in `Dockerfile.bundle` so laptop + cluster
stay in sync.

## 6. Wall-clock / GPU size

Defaults in `slurm/gpu-t4.sbatch` target a single T4 for 30 minutes.
For models baked in at `/opt/model`, size the GPU by the **final
weights**, not by `MODEL_REPO` code size:

| Final weights | Suggested GPU | Wall-clock |
|---------------|---------------|------------|
| ≤ 7 B (~15 GiB) | `T4:1` | 30 min |
| 7–13 B | `A40:1` | 1 h |
| 30 B+ | `A100:2` or `A100fat:1` | 2 h |

```diff
-#SBATCH --time=0-00:30:00
-#SBATCH --gpus-per-node=T4:1
-#SBATCH --mem=32G
+#SBATCH --time=0-02:00:00
+#SBATCH --gpus-per-node=A100:2
+#SBATCH --mem=120G
```

## 7. Add a second SIF flavour (CPU-only vs CUDA)

Useful when you want a small CPU-only bundle for testing / CI next
to the heavy CUDA bundle.

Create `apptainer/bundle-cpu.def`:

```bash
cp apptainer/bundle.def apptainer/bundle-cpu.def
```

Edit the first line:

```diff
-Bootstrap: docker
-From: nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04
+Bootstrap: docker
+From: python:3.12-slim-bookworm
```

Wrap the build script:

```bash
# scripts/build-sif-cpu.sh
#!/usr/bin/env bash
set -euo pipefail
[ -f .env ] && { set -a; . ./.env; set +a; }
: "${MODEL_REPO:?}"
: "${MODEL_REF:=main}"
apptainer build \
    --build-arg MODEL_REPO="$MODEL_REPO" \
    --build-arg MODEL_REF="$MODEL_REF" \
    "${1:-bundle-cpu.sif}" apptainer/bundle-cpu.def
```

Run CPU tests without a GPU allocation:

```bash
apptainer run bundle-cpu.sif pixi run smoke
```

Keep the CUDA `bundle.sif` for real inference; the CPU variant is
for correctness tests that shouldn't burn GPU hours.

## 8. Skip `.git` vs. keep it

The default `%post` ends with `rm -rf /opt/model/.git` to shrink the
SIF. If you need to run `git describe` or LFS-fetch deferred files
at runtime, comment that line out — at the cost of a larger SIF
(often 2-3 × bigger for LFS repos).

## 9. Swap `MODEL_DIR`

**Do not.** `/opt/model` is hard-coded in `src/infer_git_model/`
(via `MODEL_DIR` env var with that default), in the bundle def, in
the Dockerfile, and in the sbatch. Every downstream example that
consumes a bundle expects this path.

## 10. What NOT to change

- `generate()` return shape `{text, model, device, usage}` — the
  canonical V3SE inference contract. Add keys, don't remove.
- `MODEL_DIR=/opt/model` — see §9.
- Env-var names `MODEL_REPO`, `MODEL_REF`, `HF_TOKEN`. They are read
  by three separate files (`.env`, `bundle.def`, `Dockerfile.bundle`).
