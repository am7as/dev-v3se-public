# Usage — `01-foundation` (step-by-step, zero to results)

A complete walkthrough from an empty folder to a green run manifest in
all three C3SE execution modes: Docker on your laptop, Apptainer on your
laptop, and Apptainer inside an sbatch job on Alvis. This example has
no AI and no data — its only job is to prove that your container +
bind-mounts + Cephyr + Slurm plumbing works end-to-end before you bolt
a real workload on top.

## 1. What you'll end up with

- A run manifest JSON at `$RESULTS_DIR/manifest-<timestamp>.json`
  containing CPU/GPU/Python info plus the env vars that matter.
- The same manifest produced by three independent modes (Docker / local
  Apptainer / Alvis Apptainer), confirming that your dev loop is sound.
- Zero model weights, zero dataset — just plumbing.

## 2. Prerequisites

**On laptop** (dev loop):

- Docker Desktop (Windows / macOS) or Docker Engine (Linux).
- `git` (any recent version).
- Optional: Apptainer on WSL2 / Linux if you want to reproduce the SIF
  run locally. On macOS, skip local Apptainer and build on Alvis.

**On cluster**:

- C3SE account with an Alvis allocation (`<PROJECT_ID>` = your NAISS
  project ID, typically `NAISS2024-22-xxxx`).
- Cephyr home under `/cephyr/users/<cid>/Alvis/` and a Mimer group
  directory under `/mimer/NOBACKUP/groups/<naiss-id>/`.
- SSH access to `alvis1.c3se.chalmers.se` or `alvis2.c3se.chalmers.se`.

## 3. Clone the template

From inside the template tree, pick a sibling folder for your copy.

**PowerShell (Windows):**

```powershell
Copy-Item . ..\my-foundation -Recurse
cd ..\my-foundation
```

**bash / zsh (macOS / Linux):**

```bash
cp -r . ../my-foundation
cd ../my-foundation
```

## 4. Configure `.env`

**PowerShell:**

```powershell
Copy-Item .env.example .env
```

**bash / zsh:**

```bash
cp .env.example .env
```

Edit `.env` and set the cluster-side keys. Paths below use placeholders
— replace `<cid>` with your Chalmers ID and `<naiss-id>` with your
NAISS project.

```ini
# Container paths — leave as-is unless you know why.
DATA_DIR=/data
RESULTS_DIR=/results
MODELS_DIR=/models
WORKSPACE_DIR=/workspace
LOG_LEVEL=INFO

# Host bind mounts — leave blank for sibling defaults (../data, ...)
DATA_HOST=
RESULTS_HOST=
MODELS_HOST=

# Cephyr (code) and Mimer (data/weights/results) — used by sync scripts
# and by the Alvis side of the workflow.
CEPHYR_USER=<cid>
CEPHYR_PROJECT_PATH=/cephyr/users/<cid>/Alvis/my-foundation
CEPHYR_TRANSFER_HOST=alvis2.c3se.chalmers.se
ALVIS_LOGIN_HOST=alvis2.c3se.chalmers.se
ALVIS_ACCOUNT=<naiss-id>
MIMER_GROUP_PATH=/mimer/NOBACKUP/groups/<naiss-id>
MIMER_PROJECT_PATH=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-foundation

JUPYTER_PORT=7888
```

Then fix the Slurm `--account` placeholder in every sbatch:

```diff
-#SBATCH --account=<PROJECT_ID>
+#SBATCH --account=<naiss-id>
```

Apply to `slurm/cpu-smoke.sbatch` and `slurm/gpu-smoke.sbatch`.

## 5. Laptop smoke test (Docker)

Bring the dev container up and run the smoke task.

**PowerShell:**

```powershell
docker compose up -d dev
docker compose exec dev pixi install
docker compose exec dev pixi run smoke
Get-Content ..\results\manifest-*.json | Select-Object -First 40
```

**bash / zsh:**

```bash
docker compose up -d dev
docker compose exec dev pixi install
docker compose exec dev pixi run smoke
head -n 40 ../results/manifest-*.json
```

Expected: a JSON manifest prints a timestamped filename, the paths
resolve to `/data`, `/results`, `/models`, and the `runtime` section
shows `in_slurm: false`. On a laptop the `gpu` array is typically empty
unless you un-commented the nvidia block in `docker-compose.yml`.

## 6. Build the SIF (local Apptainer — optional)

If you have Apptainer on WSL2 / Linux and want to verify mode 2 before
pushing to the cluster:

```bash
apptainer build dev.sif apptainer/dev.def
apptainer run --bind .:/workspace dev.sif pixi install
apptainer run --bind .:/workspace dev.sif pixi run smoke
```

On macOS / Windows without local Apptainer, skip this step — the
Alvis-side build in section 8 covers mode 3.

## 7. Push to cluster

### Git (preferred)

```bash
git init -b main
git add .env.example .gitignore pixi.toml pyproject.toml README.md \
        apptainer/ configs/ docker-compose.yml docs/ scripts/ slurm/ \
        src/ tests/
git commit -m "initial foundation scaffold"
git remote add origin git@github.com:<team>/my-foundation.git
git push -u origin main
```

Then on the cluster:

```bash
ssh <cid>@alvis2.c3se.chalmers.se
mkdir -p /cephyr/users/<cid>/Alvis
cd /cephyr/users/<cid>/Alvis
git clone git@github.com:<team>/my-foundation.git
cd my-foundation
```

Copy your `.env` (never committed) from laptop to cluster.

**PowerShell:**

```powershell
scp .env <cid>@alvis2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/my-foundation/.env
```

**bash / zsh:**

```bash
scp .env <cid>@alvis2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/my-foundation/.env
```

### rsync (fallback — solo workflow, no remote)

Use the shipped helper from the laptop:

```bash
bash ../../_shared/scripts/sync-to-cephyr.sh
```

It reads `CEPHYR_USER` / `CEPHYR_PROJECT_PATH` from `.env` and rsyncs
the tree over `alvis2.c3se.chalmers.se`, excluding `.git`, `.pixi`,
`results/`, and `models/`.

## 8. Cluster setup (build the SIF on Alvis)

SSH to Alvis, then build the dev SIF. Point the Apptainer cache at
Mimer to avoid hammering your 30 GiB / 60k-file Cephyr quota.

```bash
ssh <cid>@alvis2.c3se.chalmers.se
cd /cephyr/users/<cid>/Alvis/my-foundation

export APPTAINER_CACHEDIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/apptainer-cache
mkdir -p "$APPTAINER_CACHEDIR"

apptainer build dev.sif apptainer/dev.def
```

First build: 2-5 minutes (pulls the base Pixi image, installs OS deps).
The resulting `dev.sif` is ~700 MB — it lives in your Cephyr checkout,
so keep an eye on quota with `C3SE_quota`.

## 9. Cluster smoke (CPU then GPU)

Start with the CPU job — it's fastest and exercises bind mounts without
needing a GPU queue slot:

```bash
sbatch slurm/cpu-smoke.sbatch
squeue -u $USER                       # wait for R, then CG
ls slurm-foundation-cpu-smoke-*.out
cat slurm-foundation-cpu-smoke-*.out
```

Expected: the manifest JSON echoes with paths `/data`, `/results`,
`/models`, and `runtime.in_slurm: true`.

Then the T4 GPU job:

```bash
sbatch slurm/gpu-smoke.sbatch
squeue -u $USER
cat slurm-foundation-gpu-smoke-*.out
```

Expected: `runtime.in_slurm: true` AND `gpu` contains one entry with
`name: "Tesla T4"`, memory ~15 GB. If `gpu` is empty despite the T4
allocation, the `--nv` flag is probably missing from the sbatch's
`apptainer run` line.

## 10. Run the real workload

For `01-foundation`, the "real workload" IS the smoke — there's no
model or data. Re-run `pixi run smoke` with different allocations to
characterize what you'd need later:

```bash
# A100 40GB instead of T4 — edit the sbatch or use --export:
sbatch --export=ALL --gpus-per-node=A40:1 slurm/gpu-smoke.sbatch

# 2x T4 for multi-GPU visibility:
sbatch --export=ALL --gpus-per-node=T4:2 slurm/gpu-smoke.sbatch
```

Each run drops a fresh `manifest-<ts>.json` in `$RESULTS_DIR`. You can
diff them to confirm the allocation you requested is what showed up.

When you graduate to real work, replace `scripts/smoke.py` with your
entrypoint and keep the manifest — it's a cheap provenance record.

## 11. Retrieve results

From the laptop, pull `results/` back. The manifest files are tiny
(KB-scale), so rsync finishes in seconds.

**PowerShell:**

```powershell
rsync -avh --progress `
  <cid>@alvis2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/my-foundation/results/ `
  .\results\
```

**bash / zsh:**

```bash
rsync -avh --progress \
  <cid>@alvis2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/my-foundation/results/ \
  ./results/
```

Or use the helper:

```bash
bash ../../_shared/scripts/sync-from-cephyr.sh
```

Inspect any manifest:

**PowerShell:**

```powershell
Get-Content .\results\manifest-*.json | Select-String '"name"'
```

**bash / zsh:**

```bash
jq '.gpu, .runtime' results/manifest-*.json
```

## 12. Verification checklist

- [ ] `.env` is filled in and NOT committed (check `git status`).
- [ ] Every `slurm/*.sbatch` has your real `--account=<naiss-id>`.
- [ ] Docker smoke wrote `../results/manifest-*.json` with `in_slurm: false`.
- [ ] `apptainer build dev.sif apptainer/dev.def` on Alvis completed
      and `ls -lh dev.sif` shows a ~500 MB-2 GB file.
- [ ] `APPTAINER_CACHEDIR` pointed at Mimer during the build (check
      `C3SE_quota` — Cephyr should not have grown by the cache size).
- [ ] `slurm/cpu-smoke.sbatch` job reached state `CG`/`CD` and the
      `.out` file contains a manifest with `in_slurm: true`.
- [ ] `slurm/gpu-smoke.sbatch` manifest lists a Tesla T4 in the `gpu`
      array.
- [ ] `results/` synced back to the laptop and every manifest opens.

## 13. Troubleshooting

- **`docker compose exec dev ...` says "no such container"** → run
  `docker compose up -d dev` first, then retry. Check `docker ps`.
- **`pixi install` hangs on "Solving environment"** → first solve can
  take 5-10 min. Subsequent runs hit the persistent `pixi_env` volume
  and are instant.
- **`apptainer build` on Alvis fails with "no space left on device"**
  → you forgot to set `APPTAINER_CACHEDIR` to Mimer. Unset it and
  re-export pointing at `/mimer/NOBACKUP/groups/<naiss-id>/<cid>/...`,
  then `rm -rf ~/.apptainer/cache` and rebuild.
- **Sbatch errors with `sbatch: error: invalid account`** → the
  `--account=<PROJECT_ID>` placeholder in the sbatch wasn't replaced
  with your real NAISS ID. `grep -r '<PROJECT_ID>' slurm/` to find
  any stragglers.
- **Cephyr quota warning after a few builds** → `dev.sif` lives next
  to the code. Move it to Mimer and symlink if you rebuild often:
  `mv dev.sif /mimer/NOBACKUP/groups/<naiss-id>/<cid>/sif/ && ln -s /mimer/NOBACKUP/groups/<naiss-id>/<cid>/sif/dev.sif .`
- **GPU manifest shows `gpu: []` despite requesting a T4** → the
  `apptainer run` line is missing `--nv`. Check `slurm/gpu-smoke.sbatch`
  and confirm `--nv` precedes the `--bind` flags.
