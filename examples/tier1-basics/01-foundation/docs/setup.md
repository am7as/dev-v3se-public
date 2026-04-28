# Setup — `01-foundation`

From a fresh clone to a green smoke test, on both laptop and Alvis.

## Part A — Laptop

### Prerequisites

- Docker Desktop (Windows 10/11 or macOS/Linux)
- Git
- (Optional but recommended) Apptainer on WSL2 / Linux if you want to
  test the cluster path locally.

### Step 1 — Clone the template

```powershell
Copy-Item <path-to-templates>\tier1-basics\01-foundation ..\my-project -Recurse
cd ..\my-project
```

### Step 2 — Create sibling data folders

Defaults assume `data/`, `results/`, `models/` sit next to the project:

```powershell
New-Item -ItemType Directory -Path ..\data, ..\results, ..\models -Force | Out-Null
```

Skip if you prefer to override via `.env` — see
[`docs/../../../docs/data-patterns.md`](../../../docs/data-patterns.md)
*(added in Phase B)*.

### Step 3 — Copy `.env.example` → `.env`

```powershell
Copy-Item .env.example .env
```

Most defaults work as-is. Fill in `CEPHYR_USER` if you'll sync to Alvis;
leave blank otherwise.

### Step 4 — Bring the dev container up

```powershell
docker compose up -d dev
docker compose exec dev pixi install
```

`pixi install` takes a minute on first run (downloads Python + deps into
the persistent `pixi_env` volume).

### Step 5 — Run the smoke test

```powershell
docker compose exec dev pixi run smoke
```

Expected output: CPU info, GPU info (none on most laptops), Python
version, path info, and a line like `manifest : /results/manifest-<ts>.json`.

Verify on host:

```powershell
ls ..\results\
# manifest-20260418T140203Z.json
cat ..\results\manifest-*.json
```

### Step 6 — Run the tests

```powershell
docker compose exec dev pixi run test
```

Four passing tests.

## Part B — Alvis

### Prerequisites

- C3SE Alvis allocation with a project id (e.g., `NAISS2024-5-123`).
- SSH access to `alvis1.c3se.chalmers.se` / `alvis2.c3se.chalmers.se`.
- The laptop side already working (Part A green).

### Step 1 — Configure Cephyr sync

In `.env`:

```ini
CEPHYR_USER=<your-cid>
CEPHYR_PROJECT_PATH=/cephyr/users/<your-cid>/Alvis/foundation
```

### Step 2 — Sync to Cephyr

```bash
bash ../../_shared/scripts/sync-to-cephyr.sh
```

(Or from the project root if you've copied `_shared/` alongside: adjust
the relative path.)

### Step 3 — SSH in and build the SIF

```bash
ssh <cid>@alvis2.c3se.chalmers.se
cd /cephyr/users/<cid>/Alvis/foundation
apptainer build dev.sif apptainer/dev.def
```

First build: 2–5 minutes. Subsequent builds much faster.

### Step 4 — Fix the Slurm account

Edit `slurm/gpu-smoke.sbatch`:

```diff
-#SBATCH --account=<PROJECT_ID>
+#SBATCH --account=NAISS2024-5-123
```

Do the same in `slurm/cpu-smoke.sbatch`.

### Step 5 — Submit the CPU smoke

```bash
sbatch slurm/cpu-smoke.sbatch
squeue -u $USER
```

When it finishes (5 minutes max), check the output file:

```bash
cat slurm-foundation-cpu-smoke-<jobid>.out
```

Expected: the same CPU/path info as the laptop run. `gpus : none detected`.

### Step 6 — Submit the GPU smoke

```bash
sbatch slurm/gpu-smoke.sbatch
```

After ~1–5 minutes of queue time:

```bash
cat slurm-foundation-gpu-smoke-<jobid>.out
```

Expected: `gpus : 1 via nvidia-smi` followed by the T4 details and
`manifest : /results/manifest-<ts>.json`.

### Step 7 — Inspect the manifest

```bash
ls results/
cat results/manifest-*.json
```

Look for:
- `gpu[0].name`: `Tesla T4`
- `runtime.in_slurm`: `true`
- `runtime.slurm_node`: `alvis1-<num>`

## Part C — Bring results home

```powershell
# On laptop, from project root:
rsync -avh --progress \
    <cid>@alvis2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/foundation/results/ \
    .\results-from-alvis\
```

## Done

You've just proven end-to-end plumbing works: code on laptop, dev
container, Apptainer on Alvis, Slurm, GPU, manifest writes. Every other
template in this library inherits this foundation.

Next: read [usage.md](usage.md) for the day-to-day loop.
