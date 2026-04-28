# `04-data-cephyr` — data workflow on Cephyr

Extends `01-foundation` with the data-handling workflow. No AI. Shows:

- How to point `/data` at different host sources (local / Cephyr private
  / Cephyr shared `/mimer`).
- A tiny ETL-style job: read CSVs under `$DATA_DIR`, compute summary
  statistics, write aggregated output to `$RESULTS_DIR`.
- Quota-safe patterns: when to process in-place vs. stream, how to check
  quotas mid-run, how to clean up.

## What's new vs foundation

- `src/data_cephyr/processing.py` — the ETL logic (stateless, stream-y).
- `scripts/process.py` — `pixi run process` entrypoint.
- `configs/datasets.toml` — declares which data source to read from.
- `slurm/process-cpu.sbatch` — CPU-only Alvis job (no GPU for ETL).
- `data/sample/*.csv` — 3 tiny CSVs so the template runs out-of-the-box.

## Quickstart

```powershell
Copy-Item . ..\my-project -Recurse
cd ..\my-project
Copy-Item .env.example .env
docker compose up -d dev
docker compose exec dev pixi install
docker compose exec dev pixi run process --source sample
cat ..\results\summary.json
```

Expected output: counts per column, min/max per numeric column, written
as JSON.

## On Alvis: bind different sources at will

### Private Cephyr data (your own)

```bash
# Edit sbatch: add a --bind pointing at where your real data sits
apptainer run --bind .:/workspace \
    --bind /cephyr/users/$USER/Alvis/my-data:/data \
    dev.sif pixi run process --source private
```

### Shared `/mimer` dataset (read-only)

```bash
apptainer run --bind .:/workspace \
    --bind /mimer/NOBACKUP/Datasets/my-shared-dataset:/data:ro \
    dev.sif pixi run process --source shared
```

Read-only mount means your code can't accidentally write into the
shared dataset (good — it's read-only on the filesystem anyway).

## When to leave this template

- Need multiple data sources in one pipeline (e.g., join shared + private)
  → `12-multi-source-data`.
- Need AI inference on the data → combine with `02`/`03`/`11`.
