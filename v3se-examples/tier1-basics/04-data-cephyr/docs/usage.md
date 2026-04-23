# Usage — `04-data-cephyr` (step-by-step, zero to results)

A complete walkthrough from an empty folder to a computed
`summary.json` over CSV data, exercising V3SE's three canonical data
sources: the shipped sample, your private data on Cephyr, and a
read-only shared dataset on Mimer. There is no AI in this template —
its job is to nail down the bind-mount story.

## 1. What you'll end up with

- `$RESULTS_DIR/summary.json` listing file counts, row counts, and
  per-column stats for your source.
- A working sbatch that binds any combination of Cephyr private data +
  Mimer shared data + Mimer project outputs into the container.
- A quota-safe pattern: read-only for shared data, writes confined to
  Mimer project space, code on Cephyr.

## 2. Prerequisites

**On laptop** (dev loop):

- Docker Desktop (Windows / macOS) or Docker Engine (Linux).
- `git`.

**On cluster**:

- C3SE account with Alvis allocation (`<PROJECT_ID>` = NAISS ID).
- Cephyr home under `/cephyr/users/<cid>/Alvis/` (code + SIF).
- Mimer group directory `/mimer/NOBACKUP/groups/<naiss-id>/` (data,
  results, large files).
- SSH to `alvis2.c3se.chalmers.se`.

## 3. Clone the template

**PowerShell (Windows):**

```powershell
Copy-Item . ..\my-data-project -Recurse
cd ..\my-data-project
```

**bash / zsh (macOS / Linux):**

```bash
cp -r . ../my-data-project
cd ../my-data-project
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

Edit `.env` — include the Mimer paths that the sbatch will bind:

```ini
# Container paths (don't change).
DATA_DIR=/data
RESULTS_DIR=/results
MODELS_DIR=/models
WORKSPACE_DIR=/workspace
LOG_LEVEL=INFO

# Host bind mounts — blank for sibling defaults (laptop only).
DATA_HOST=
RESULTS_HOST=
MODELS_HOST=

# Cephyr (code) + Alvis login.
CEPHYR_USER=<cid>
CEPHYR_PROJECT_PATH=/cephyr/users/<cid>/Alvis/my-data-project
CEPHYR_TRANSFER_HOST=vera2.c3se.chalmers.se
ALVIS_LOGIN_HOST=alvis2.c3se.chalmers.se
ALVIS_ACCOUNT=<naiss-id>

# Mimer (data, results) — canonical V3SE split.
MIMER_GROUP_PATH=/mimer/NOBACKUP/groups/<naiss-id>
MIMER_PROJECT_PATH=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-data-project

# Which logical dataset to process (matches configs/datasets.toml).
DATASET=sample

JUPYTER_PORT=7888
```

Fix the Slurm `--account` placeholder in `slurm/process-cpu.sbatch`:

```diff
-#SBATCH --account=<PROJECT_ID>
+#SBATCH --account=<naiss-id>
```

## 5. Laptop smoke test

Bring up the container, install deps, process the shipped 3-CSV
sample.

**PowerShell:**

```powershell
docker compose up -d dev
docker compose exec dev pixi install
docker compose exec dev pixi run smoke
docker compose exec dev pixi run process --source sample
Get-Content ..\results\summary.json
```

**bash / zsh:**

```bash
docker compose up -d dev
docker compose exec dev pixi install
docker compose exec dev pixi run smoke
docker compose exec dev pixi run process --source sample
cat ../results/summary.json
```

Expected: `summary.json` reports 3 files, 12 rows total, with
per-column dtypes and per-numeric min/max. Raw sample CSVs stay
untouched in `data/sample/`.

## 6. Build step (not applicable)

No image bake. Dev-mode SIF is bind-mounted. Skip to section 8 for the
Alvis-side build.

## 7. Push to cluster

### Git (preferred)

Don't commit heavy data. The default `.gitignore` already excludes
`data/` at the tree root EXCEPT the `data/sample/` subdirectory
that ships with this example. Adjust as needed.

```bash
git init -b main
git add .env.example .gitignore pixi.toml pyproject.toml README.md \
        apptainer/ configs/ data/sample/ docker-compose.yml docs/ \
        scripts/ slurm/ src/ tests/
git commit -m "initial data-cephyr scaffold"
git remote add origin git@github.com:<team>/my-data-project.git
git push -u origin main
```

On cluster:

```bash
ssh <cid>@alvis2.c3se.chalmers.se
mkdir -p /cephyr/users/<cid>/Alvis
cd /cephyr/users/<cid>/Alvis
git clone git@github.com:<team>/my-data-project.git
cd my-data-project
scp <cid>@<laptop-hostname>:.env .   # or scp from laptop — never commit
```

### rsync (fallback)

```bash
bash ../../_shared/scripts/sync-to-cephyr.sh
```

### Stage real data to Mimer (NOT Cephyr)

Private/large data goes to Mimer — Cephyr is for code only (30 GiB /
60k file quota). Use the helper:

```bash
bash ../../_shared/scripts/sync-to-mimer.sh ./my-local-data/ /mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-data-project/raw/
```

Or directly via rsync:

**PowerShell:**

```powershell
rsync -avh --progress `
  .\my-local-data\ `
  <cid>@vera2.c3se.chalmers.se:/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-data-project/raw/
```

**bash / zsh:**

```bash
rsync -avh --progress \
  ./my-local-data/ \
  <cid>@vera2.c3se.chalmers.se:/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-data-project/raw/
```

## 8. Cluster setup

SSH in, aim the Apptainer cache at Mimer, build the dev SIF:

```bash
ssh <cid>@alvis2.c3se.chalmers.se
cd /cephyr/users/<cid>/Alvis/my-data-project

export APPTAINER_CACHEDIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/apptainer-cache
mkdir -p "$APPTAINER_CACHEDIR"

apptainer build dev.sif apptainer/dev.def
```

First build: 2-5 min.

Create your project space on Mimer if it doesn't exist:

```bash
mkdir -p /mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-data-project/{raw,results,apptainer-cache}
```

## 9. Cluster smoke

Start with the shipped `sample` source — it ships with the repo, so
it's already on Cephyr once you pushed:

```bash
sbatch slurm/process-cpu.sbatch
squeue -u $USER
cat slurm-data-cephyr-*.out
```

Expected: the job completes in seconds and `results/summary.json` on
Cephyr holds the same output you saw on the laptop.

## 10. Run the real workload

Now exercise the V3SE bind pattern. Edit
`slurm/process-cpu.sbatch` to bind the three canonical sources. The
shipped sbatch has ready-to-uncomment blocks — replace its final
`apptainer run ...` line with whichever variant fits.

### A) Private Cephyr data

Small/active datasets that you own. Read-write.

```bash
apptainer run \
    --bind .:/workspace \
    --bind /cephyr/users/<cid>/Alvis/my-data-private:/data \
    --bind /mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-data-project/results:/results \
    "$SIF" pixi run process --source private
```

### B) Shared `/mimer` dataset (read-only)

C3SE-maintained public corpora under `/mimer/NOBACKUP/Datasets/...`,
or your group's shared cold storage.

```bash
apptainer run \
    --bind .:/workspace \
    --bind /mimer/NOBACKUP/Datasets/my-shared-dataset:/data:ro \
    --bind /mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-data-project/results:/results \
    "$SIF" pixi run process --source shared
```

The `:ro` suffix is belt-and-braces — `/mimer/NOBACKUP/Datasets` is
filesystem-level read-only, but binding RO means local code bugs
can't even try a write.

### C) Three-source job (shared + private + project outputs)

The V3SE canonical split: Cephyr for code, Mimer group for shared
data, Mimer project for your results.

```bash
apptainer run \
    --bind .:/workspace \
    --bind /mimer/NOBACKUP/Datasets/my-shared-dataset:/data/shared:ro \
    --bind /cephyr/users/<cid>/Alvis/my-data-private:/data/private \
    --bind /mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-data-project/results:/results \
    "$SIF" pixi run process --source shared
```

Your Python code always sees `/data/shared` and `/data/private`
regardless of the host layout — so `scripts/process.py` never hard-
codes a `/cephyr/...` or `/mimer/...` path.

### Quota hygiene (before + after)

```bash
C3SE_quota
```

- **Cephyr** should not grow by the size of your data — only code +
  SIF. If it jumps, you accidentally read data into the Cephyr tree.
- **Mimer** grows with your results; it has much larger quotas.

## 11. Retrieve results

Results land in the Mimer project directory (not Cephyr). Pull from
Mimer — it's the same SSH transfer host:

**PowerShell:**

```powershell
rsync -avh --progress `
  <cid>@vera2.c3se.chalmers.se:/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-data-project/results/ `
  .\results\
```

**bash / zsh:**

```bash
rsync -avh --progress \
  <cid>@vera2.c3se.chalmers.se:/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-data-project/results/ \
  ./results/
```

Or use the helper (reads `.env` for paths):

```bash
bash ../../_shared/scripts/sync-from-cephyr.sh
```

Inspect:

**PowerShell:**

```powershell
Get-Content .\results\summary.json
```

**bash / zsh:**

```bash
jq . results/summary.json
```

## 12. Verification checklist

- [ ] `.env` lists real `MIMER_GROUP_PATH` and `MIMER_PROJECT_PATH`
      (not committed).
- [ ] `slurm/process-cpu.sbatch` has real `--account=<naiss-id>`.
- [ ] Laptop `pixi run process --source sample` produced
      `../results/summary.json` with 3 files and 12 rows.
- [ ] `dev.sif` built on Alvis; `APPTAINER_CACHEDIR` set to Mimer
      during build; Cephyr quota unchanged by the cache.
- [ ] Cluster sbatch completed for sample source and wrote a summary.
- [ ] Choose a bind variant (A / B / C) that matches your real data
      layout; edit the sbatch and rerun.
- [ ] Results sync back to laptop; `summary.json` reflects real data.
- [ ] `C3SE_quota` still shows Cephyr well under 30 GiB / 60k files.

## 13. Troubleshooting

- **`FileNotFoundError: /data/sample`** inside a run → the sbatch
  didn't bind `/data` to a directory containing `sample/`. For the
  shipped run-from-repo case, the container sees the `.` bind mount
  as `/workspace`; the script falls back to `$DATA_DIR` if the
  subdir isn't there. Check the `--bind` in the `apptainer run` line.
- **Write errors on `/data/...`** when using pattern B → you tried to
  write back to a `:ro` mount. Direct writes to
  `$RESULTS_DIR` (which should be bound to Mimer, not Cephyr).
- **Cephyr quota spike** → someone staged raw data to `data/` inside
  the Cephyr checkout. Move it to
  `/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-data-project/raw/` and
  bind from there.
- **`permission denied` reading a Mimer shared dataset** → the
  dataset is owned by another group and you're not in the ACL.
  Confirm with `ls -ld /mimer/NOBACKUP/Datasets/<name>` and ask C3SE
  to add you, or switch to a different dataset.
- **CSV parse errors** → `pandas` inferred a bad dtype. Add
  `dtype={...}` or `on_bad_lines='skip'` in `src/data_cephyr/processing.py`.
- **Results directory is empty after the job** → the sbatch's
  `$RESULTS_DIR` resolved to `$PWD/results` (Cephyr) instead of your
  Mimer project path. Explicitly `export RESULTS_DIR=/mimer/...` in
  the sbatch before `apptainer run`, or pass
  `--bind <mimer>:/results`.
