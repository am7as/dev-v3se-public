# `01-foundation` — folder layout

```
01-foundation/
├── README.md                   why-this-template + quickstart
├── .env.example                every env var the template reads, with comments
├── .gitignore
├── docker-compose.yml          laptop dev stack
├── pixi.toml                   package manager config
├── pyproject.toml              Python packaging + tool configs
├── apptainer/
│   ├── dev.def                 dev-mode Apptainer recipe (code bind-mounted)
│   └── app.def                 deployment Apptainer recipe (code baked in)
├── configs/
│   └── config.toml             layout config (paths inside container)
├── scripts/                    entrypoints invoked by `pixi run <task>`
│   ├── smoke.py                pixi run smoke
│   └── info.py                 pixi run info
├── src/foundation/             the Python package
│   ├── __init__.py
│   ├── config.py               central path resolver (data_dir, results_dir, …)
│   ├── devices.py              CPU + GPU + runtime + env collector
│   └── manifest.py             builds + writes the manifest JSON
├── slurm/
│   ├── cpu-smoke.sbatch        Alvis CPU-only smoke (5 min, no GPU)
│   └── gpu-smoke.sbatch        Alvis 1× T4 smoke (10 min)
├── tests/
│   └── test_smoke.py           pytest smoke — runs inside container
└── docs/
    ├── structure.md            (this file)
    ├── setup.md                first-time setup (laptop + Alvis)
    ├── usage.md                step-by-step golden path
    ├── modification.md         how to adapt to your project
    └── troubleshooting.md      known V3SE-specific issues
```

## Design conventions (keep these stable)

- **Container paths are fixed**: `/workspace`, `/data`, `/results`, `/models`.
  The Python code never hardcodes host paths — only these four. The mapping
  from host paths to these is driven by `.env`.
- **All entrypoints are `pixi run <task>`**: `smoke`, `info`, `test`, `lint`.
  Other templates extend this list (`infer`, `train`, etc.) but keep the
  canonical four.
- **Python code lives under `src/<package>/`**. Scripts under `scripts/`
  are thin wrappers around `src/<package>/` functions. That way, the core
  logic is importable from tests and notebooks; scripts are just
  command-line surfaces.
- **Every environment variable the code reads has a default.** If missing,
  the code either uses a sensible fallback or raises early with a clear
  message. Read `src/foundation/config.py` for the complete list.

## What sits where

| File                            | Purpose                                              |
|---------------------------------|------------------------------------------------------|
| `docker-compose.yml`            | Laptop-only. Reads `.env` for host paths.            |
| `apptainer/dev.def`             | Dev-mode SIF (used on laptop + Alvis).               |
| `apptainer/app.def`             | Deployment SIF (used for reproducible runs).         |
| `slurm/*.sbatch`                | Run on Alvis. They `apptainer run ... pixi run smoke`. |
| `src/foundation/config.py`      | Any code that needs a path imports from here.        |
| `src/foundation/devices.py`     | Gathers CPU/GPU info without requiring torch.        |
| `src/foundation/manifest.py`    | Builds + persists the run manifest.                  |
| `scripts/smoke.py`              | User-facing golden path.                             |
| `tests/test_smoke.py`           | What CI (and the smoke task) exercises.              |
