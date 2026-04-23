# `01-foundation` — V3SE project skeleton

**What it is:** the minimal scaffold every V3SE project inherits. It has
no AI model, no real dataset, no science. It's here to prove your
container + env + Cephyr + Slurm plumbing works end-to-end before you
add anything interesting on top.

**What it does:** `pixi run smoke` collects device info (CPU / GPU count,
names, memory, Python version, env vars that matter) and writes a
manifest JSON to `$RESULTS_DIR/manifest-<timestamp>.json`.

**You'll know it works when:**

1. Locally in Docker: `docker compose exec dev pixi run smoke` → green.
2. Locally in Apptainer: `apptainer run --bind .:/workspace dev.sif pixi run smoke` → green.
3. On Alvis: `sbatch slurm/gpu-t4.sbatch` produces a manifest that
   lists the T4 GPU.

## Quickstart

```powershell
# Clone this template somewhere new
Copy-Item . ..\my-project -Recurse
cd ..\my-project

# Bootstrap
Copy-Item .env.example .env
# (edit .env if you want non-default paths)

# Laptop dev loop
docker compose up -d dev
docker compose exec dev pixi install
docker compose exec dev pixi run smoke

# See the result
cat results/manifest-*.json
```

## What to change to make this yours

- `pyproject.toml` and `pixi.toml` — rename the package (currently
  `foundation`) to your project name. Keep the layout.
- `src/foundation/` → `src/<your_pkg>/`
- `configs/config.toml` — adjust dataset defaults as needed.
- `slurm/*.sbatch` — set `--account=<PROJECT_ID>` to your C3SE project.
- `.env.example` — add your template-specific keys.

Full guide: [docs/modification.md](docs/modification.md).

## Docs

| Topic                              | File                                  |
|------------------------------------|---------------------------------------|
| Folder layout explained            | [docs/structure.md](docs/structure.md) |
| First-time setup (laptop + Alvis)  | [docs/setup.md](docs/setup.md)        |
| Step-by-step usage                 | [docs/usage.md](docs/usage.md)        |
| Adapting to your project           | [docs/modification.md](docs/modification.md) |
| When things go wrong               | [docs/troubleshooting.md](docs/troubleshooting.md) |

## Status

- ✅ Docker dev mode — tested on Windows 11.
- ⏳ Local Apptainer — pending (requires Apptainer on WSL2 or Linux laptop).
- ⏳ Alvis — pending (requires user's C3SE allocation and a real `--account`).
