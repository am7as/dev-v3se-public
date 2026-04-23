# Usage — `01-foundation`

The daily loop, once setup is done.

## Pixi tasks (canonical across all templates)

| Task             | What it does                                    |
|------------------|-------------------------------------------------|
| `pixi run smoke` | Collect + print + persist the run manifest     |
| `pixi run info`  | Dump the manifest to stdout (no side effects)  |
| `pixi run test`  | Run pytest over `tests/`                        |
| `pixi run lint`  | Bytecode-compile everything (catches syntax)    |

Invoke inside the container:

```powershell
# Docker on laptop
docker compose exec dev pixi run smoke
docker compose exec dev pixi run info | jq .gpu
docker compose exec dev pixi run test

# Apptainer on laptop (after apptainer build dev.sif apptainer/dev.def)
apptainer run --bind .:/workspace dev.sif pixi run smoke

# Apptainer on Alvis (inside an sbatch script — see slurm/*.sbatch)
apptainer run --nv --bind .:/workspace dev.sif pixi run smoke
```

## Interactive development

Get a shell inside the dev container:

```powershell
docker compose exec dev bash
# inside:
pixi shell          # drops you into the Pixi environment
python -c "from __PACKAGE_NAME__.manifest import build_manifest; import json; print(json.dumps(build_manifest(), indent=2))"
```

## Adding a new entrypoint

1. Write `scripts/my_task.py` — keep it thin; put logic in `src/__PACKAGE_NAME__/`.
2. Add a line under `[tasks]` in `pixi.toml`:
   ```toml
   my_task = "python scripts/my_task.py"
   ```
3. Run it: `pixi run my_task`.

## Looking at the manifest

Every `pixi run smoke` writes one JSON under `$RESULTS_DIR`. Structure:

```json
{
  "template": "__PROJECT_SLUG__",
  "timestamp": "20260418T140203Z",
  "paths":    { "data_dir": "/data", ... },
  "cpu":      { "logical_cores": 12, ... },
  "gpu":      [ { "index": 0, "name": "Tesla T4", ... } ],
  "runtime":  { "hostname": "...", "in_slurm": true, ... },
  "env":      { "DATA_DIR": "/data", ... }
}
```

Useful queries (assumes `jq` in the container):

```powershell
docker compose exec dev pixi run info | jq '.gpu | length'
docker compose exec dev pixi run info | jq '.env.CUDA_VISIBLE_DEVICES'
```

## Laptop ↔ Alvis loop

```
1. Edit on laptop
2. docker compose exec dev pixi run smoke   # confirm it runs locally
3. bash ../_shared/scripts/sync-to-cephyr.sh
4. ssh alvis2 "cd <path>; apptainer build dev.sif apptainer/dev.def" (rebuild only if deps changed)
5. ssh alvis2 "cd <path>; sbatch slurm/gpu-smoke.sbatch"
6. Wait for the job. Read the .out file.
7. rsync results back to laptop.
```

Once the smoke is green in all three modes (Docker, laptop Apptainer,
Alvis Apptainer), you've got a working V3SE project.

## Next steps

- Use this as a starting skeleton for a real project — follow
  [modification.md](modification.md).
- Or move on to Tier 1 templates that add a specific capability:
  `02-inference-api-token`, `03-hf-shared-hub`, `04-data-cephyr`,
  `05-train-lora`.
