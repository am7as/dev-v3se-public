# Usage — `14-git-model-bundle` (step-by-step, zero to results)

Clone a model repo (git-hosted, not HF-hosted), bake the weights into
a SIF (for cluster) or a Docker image (for laptop), then run it.

## 0. What you'll end up with

- `bundle.sif` (cluster-portable) or `git-model-bundle` Docker image
  (laptop-only) with model weights baked in.
- `pixi run infer --prompt "…"` loads from `/opt/model` with no
  network access.
- On cluster, `sbatch slurm/gpu-t4.sbatch` runs the bundled SIF.

## 1. Prerequisites

**Laptop**:
- Docker Desktop + git.
- Apptainer (Linux / WSL2 / macOS with macFUSE) if you'll build the
  SIF locally. Otherwise you'll build on Alvis.
- Disk ≥ 2× the model repo size.
- For private repos: SSH key or HTTPS creds to clone.

**Cluster**:
- C3SE Alvis allocation.
- Mimer space for the SIF (ultimately; Cephyr only if small).

## 2. Clone + configure

**PowerShell:**

```powershell
Copy-Item . ..\my-git-bundle -Recurse
cd ..\my-git-bundle
Copy-Item .env.example .env
```

**bash / zsh:**

```bash
cp -r . ../my-git-bundle
cd ../my-git-bundle
cp .env.example .env
```

Edit `.env`:

```ini
MODEL_REPO=https://github.com/<org>/<model-repo>.git
MODEL_REF=main                    # or a tag, commit, or LFS branch

CEPHYR_USER=<cid>
CEPHYR_PROJECT_PATH=/cephyr/users/<cid>/Alvis/my-git-bundle
MIMER_GROUP_PATH=/mimer/NOBACKUP/groups/<naiss-id>
MIMER_PROJECT_PATH=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-git-bundle
ALVIS_ACCOUNT=<naiss-id>

# Optional — only if the model-repo references HF-gated weights during its setup
HF_TOKEN=
```

Fix the sbatch account:

```diff
-#SBATCH --account=<PROJECT_ID>
+#SBATCH --account=<naiss-id>
```

## 3. Build the SIF

### Option A — on laptop (Linux / WSL2 / macOS with macFUSE)

**bash / zsh:**

```bash
apptainer --version                   # verify installed
bash scripts/build-sif.sh             # produces ./bundle.sif
```

The script reads `MODEL_REPO` and `MODEL_REF` from `.env` and runs
`apptainer build --build-arg ...`.

### Option B — on Alvis login node (recommended for big models)

```bash
git init -b main && git add . && git commit -m "initial" && git push ...
ssh alvis
cd /cephyr/users/<cid>/Alvis/my-git-bundle
scp <cid>@<laptop>:~/my-git-bundle/.env .

export APPTAINER_CACHEDIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/apptainer-cache
mkdir -p $APPTAINER_CACHEDIR
bash scripts/build-sif.sh

ls -lh bundle.sif                     # typical: 4–30 GiB
```

## 4. (Optional) Build a Docker image for laptop runs

Laptop-only; Docker doesn't run on Alvis.

**PowerShell:**

```powershell
bash scripts/build-docker.sh
docker run --gpus all -v ${PWD}:/workspace git-model-bundle pixi run infer --prompt "Hello"
```

**bash / zsh:**

```bash
bash scripts/build-docker.sh
docker run --gpus all -v "$PWD":/workspace git-model-bundle pixi run infer --prompt "Hello"
```

## 5. Move the SIF to Mimer if large

```bash
# on Alvis
mkdir -p /mimer/NOBACKUP/groups/<naiss-id>/<cid>/sifs
mv bundle.sif /mimer/NOBACKUP/groups/<naiss-id>/<cid>/sifs/
cd /cephyr/users/<cid>/Alvis/my-git-bundle
ln -sf /mimer/NOBACKUP/groups/<naiss-id>/<cid>/sifs/bundle.sif bundle.sif
```

Or from laptop if you built there:

```bash
scp bundle.sif <cid>@alvis2.c3se.chalmers.se:/mimer/NOBACKUP/groups/<naiss-id>/<cid>/sifs/
```

## 6. Laptop smoke (optional)

```bash
apptainer run --nv bundle.sif "Explain gravity"
```

(Skip `--nv` on a GPU-less laptop; it falls back to CPU — slow but
proves the bundle.)

## 7. Cluster smoke

```bash
ssh alvis
cd /cephyr/users/<cid>/Alvis/my-git-bundle
sbatch slurm/gpu-t4.sbatch
squeue -u $USER
cat slurm-*-gpu-t4-*.out
```

Expected: `device: cuda`, bundled model metadata, generated text.

## 8. Run your real prompts

```bash
sbatch --export=ALL,PROMPT="Your question" slurm/gpu-t4.sbatch
```

For batch, pair bundle.sif's `/opt/model` with your own loop code;
see the example's `scripts/infer.py`.

## 9. Retrieve results

**PowerShell:**

```powershell
rsync -avh --progress `
  <cid>@alvis2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/my-git-bundle/results/ `
  .\results\
```

**bash / zsh:**

```bash
rsync -avh --progress \
  <cid>@alvis2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/my-git-bundle/results/ \
  ./results/
```

## 10. Verification checklist

- [ ] `apptainer run bundle.sif 'ls /opt/model'` shows model files.
- [ ] `MODEL_REPO` and `MODEL_REF` in `.env` point at a clonable
      repo (try `git ls-remote` before building).
- [ ] Every `slurm/*.sbatch` has your real `--account=<NAISS>`.
- [ ] GPU smoke log shows `device: cuda` and a generated completion.
- [ ] `results/responses/*.json` entries have non-empty `text`.

## Troubleshooting

- **Clone fails during build** → the repo URL or auth is wrong.
  Test outside the build first: `git ls-remote $MODEL_REPO`.
- **git-lfs pull times out during build** → for enormous weights,
  consider baking with `--disable-cache` or pre-downloading weights
  separately and using `%files` in `apptainer/bundle.def`.
- **SIF doesn't include the weights** → the repo uses git-lfs but
  the build didn't run `git lfs pull`. Check
  `apptainer/bundle.def`'s `%post` — `git lfs pull || true` is
  there; confirm the repo actually uses LFS.
- **Runs, but `MODEL_DIR not found`** → you're using `dev.sif`, not
  `bundle.sif`. Check the sbatch's `apptainer run` line references
  `bundle.sif`.
- **Huge SIF on Cephyr** → move to Mimer (step 5).
