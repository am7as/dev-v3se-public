# `12-multi-source-data` — swap data source by config

Composes `04-data-cephyr` with a source-router. Same processing code, any
of 5 data locations:

1. **local** — files under `$DATA_DIR` (default sibling of repo)
2. **cephyr_private** — your own `/cephyr/users/<cid>/...` dir
3. **mimer_shared** — read-only shared dataset under `/mimer/NOBACKUP/Datasets/`
4. **hf_hub** — a HuggingFace dataset (downloaded to `HF_HOME`)
5. **gcs** — a Google Cloud Storage bucket via `rclone` mount

Pick via `--source <name>` or `DATASET_SOURCE` in `.env`.

## What's new

- `src/data_multi/sources/` — one module per source type.
- `src/data_multi/router.py` — resolve name → concrete Path or dataset.
- `configs/sources.yaml` — registry of known logical datasets per source.

## Quickstart

```powershell
Copy-Item . ..\my-project -Recurse
cd ..\my-project
Copy-Item .env.example .env
docker compose up -d dev
docker compose exec dev pixi install

# Use the shipped sample (local)
docker compose exec dev pixi run process --source local

# Use a HuggingFace dataset
docker compose exec dev pixi run process --source hf_hub --dataset-id imdb
```

## On Alvis

The sbatch picks what to bind:

```bash
# Local (sample shipped with template)
sbatch slurm/process-local.sbatch

# Shared (read-only /mimer)
sbatch slurm/process-mimer-shared.sbatch       # edit which dataset

# Private Cephyr
sbatch slurm/process-private.sbatch      # edit which dataset
```

## When to leave

- Also need multi-provider AI → combine with `11` in your project.
- Finetune using mixed sources → `13-train-infer-pipeline`.
