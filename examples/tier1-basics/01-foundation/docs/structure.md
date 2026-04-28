# `01-foundation` — folder layout

```
01-foundation/
├── README.md                   why-this-template + quickstart
├── .env.example                every env var the template reads, with comments
├── .gitignore                  keeps .env, results/, *.sif, .pixi/ out of git
├── docker-compose.yml          laptop dev stack
├── pixi.toml                   pixi tasks + deps
├── pyproject.toml              Python packaging + tool configs
├── apptainer/
│   ├── dev.def                 dev SIF (code bind-mounted in) — laptop + Alvis
│   └── app.def                 deployment SIF (code baked in)
├── configs/
│   └── config.toml             layout config (container paths inside the SIF)
├── scripts/                    entrypoints for `pixi run <task>`
│   ├── smoke.py                pixi run smoke   — writes manifest JSON
│   └── info.py                 pixi run info    — prints resolved env
├── src/foundation/             the Python package
│   ├── __init__.py
│   ├── config.py               central path resolver (DATA_DIR, RESULTS_DIR, …)
│   ├── devices.py              CPU + GPU + runtime + env collector
│   └── manifest.py             builds + writes the manifest JSON
├── slurm/
│   ├── cpu-smoke.sbatch        Alvis CPU-only smoke (5 min, no GPU)
│   └── gpu-smoke.sbatch        Alvis 1× T4 smoke (10 min, `--nv`)
├── tests/
│   └── test_smoke.py           pytest — config + manifest keys, no GPU needed
└── docs/
    ├── setup.md                first-time setup (laptop + Alvis)
    ├── usage.md                step-by-step golden path
    ├── modification.md         how to adapt to your project
    ├── structure.md            (this file)
    └── troubleshooting.md      known C3SE-specific issues
```

## Key files, one paragraph each

### `apptainer/dev.def` and `apptainer/app.def`

Both start from `ghcr.io/prefix-dev/pixi:0.48.0-noble`. `dev.def` installs
only system tools (`curl`, `git`, `openssh-client`, `rsync`, `tini`) and
expects your project bind-mounted at `/workspace` at run time — edit on
the host, rerun, no rebuild. `app.def` copies `src/` + `scripts/` +
`configs/` + `pixi.toml` into `/workspace` and runs `pixi install` at
build time, producing a self-contained deployment SIF. Neither SIF bakes
data or results — those come from host paths via `--bind` at run time.

### `slurm/cpu-smoke.sbatch`

5-minute CPU-only job (`--cpus-per-task=2`, `--mem=4G`, no `--gpus`).
Sets `DATA_DIR` / `RESULTS_DIR` / `MODELS_DIR` to `$PWD/data` etc. as
cheap defaults if not already set by the environment, then
`apptainer run --bind .:/workspace --bind $DATA_DIR:/data …` through the
dev SIF. `--account=<PROJECT_ID>` is a placeholder — replace before
first submission.

### `slurm/gpu-smoke.sbatch`

10-minute `T4:1` job (`--cpus-per-task=4`, `--mem=16G`). Same plumbing as
`cpu-smoke.sbatch` plus `--nv` on the `apptainer run` to expose GPUs, and
two extra env defaults (`HF_HOME`, `TRANSFORMERS_CACHE`) so a later
template that does load a model doesn't accidentally scribble into
`$HOME` on Cephyr. This example itself doesn't load a model — these
exports are muscle-memory for the ones that do.

### `src/foundation/config.py`

Env-var resolver. `data_dir()`, `results_dir()`, `models_dir()`,
`workspace_dir()` return container paths (`/data`, `/results`,
`/models`, `/workspace` by default). All other code reads paths **only**
from this module — never from `os.environ` directly.

### `src/foundation/devices.py`

Gathers CPU (`os.cpu_count`, `platform`), GPU (prefers `nvidia-smi`,
falls back to `torch.cuda` when available), runtime (hostname, Slurm
env, container markers), and relevant env vars. Works without PyTorch
installed — deliberate, so the foundation SIF stays tiny.

### `src/foundation/manifest.py`

`build_manifest()` packs config paths + `devices.collect()` into a dict;
`write_manifest()` writes it to `$RESULTS_DIR/manifest-<utc>.json`. This
manifest is the one JSON artefact `pixi run smoke` produces — later
templates follow the same pattern.

### `scripts/smoke.py` and `scripts/info.py`

`smoke.py` calls `manifest.write_manifest()` and echoes the path on
stdout — this is what the sbatch jobs execute. `info.py` dumps the same
fields as JSON to stdout without writing anything, handy for verifying
a container picked up `.env` correctly.

### `configs/config.toml`

Static layout — container paths only. Env vars override at runtime;
this file is the fallback and the record of the convention.

### `docker-compose.yml`

Laptop dev stack. Builds `../../_shared/docker/Dockerfile.dev`,
bind-mounts the project at `/workspace`, maps `$DATA_HOST` → `/data`,
`$RESULTS_HOST` → `/results`, `$MODELS_HOST` → `/models` (all default
to sibling directories if unset in `.env`), and keeps a `pixi_env`
named volume so `pixi install` doesn't re-solve on every rebuild. The
container `sleep infinity`s; you enter with `docker compose exec dev
bash` (PowerShell form: identical).

### `tests/test_smoke.py`

Offline pytest — asserts `config.data_dir()` defaults, manifest keys,
and that `relevant_env()` returns a dict. Runs under `pixi run test`
in < 1 s with no GPU, no model load.

## Storage model — what lives where on Alvis

This example is the reference for the Cephyr/Mimer split that every
downstream template inherits.

| Container path | Host path on laptop              | Host path on Alvis                                | Storage tier                           |
|----------------|----------------------------------|---------------------------------------------------|----------------------------------------|
| `/workspace`   | `.` (project root)               | `/cephyr/users/<cid>/Alvis/<project>/`            | **Cephyr** — code, ≤ 30 GiB, 60k file cap |
| `/data`        | `${DATA_HOST:-../data}`          | `/mimer/NOBACKUP/groups/<naiss-id>/data/`         | **Mimer project** — inputs             |
| `/results`     | `${RESULTS_HOST:-../results}`    | `/mimer/NOBACKUP/groups/<naiss-id>/results/`      | **Mimer project** — outputs            |
| `/models`      | `${MODELS_HOST:-../models}`      | `/mimer/NOBACKUP/groups/<naiss-id>/models/`       | **Mimer project** — weights            |
| `/mimer/NOBACKUP/Datasets/…` | (N/A)                | `/mimer/NOBACKUP/Datasets/` (read-only mirror)    | **Mimer shared** — used by `03-hf-shared-hub` |

The two invariants that matter:

- Cephyr holds **only code** (and the SIFs you build, which are large
  but few — well under the 60k file cap). The Pixi environment lives
  inside the container image on Alvis, not on Cephyr.
- Mimer holds **everything else** — datasets, model weights, result
  artefacts, `HF_HOME`, scratch. Never let a cache default to `$HOME`.

### Runtime-vs-build resolution

- **Build time** (`apptainer build …`, `docker compose build`): no host
  paths are baked in. Only code, pixi deps, system tools.
- **Compose up** (laptop): `docker-compose.yml` reads `.env` and maps
  `DATA_HOST` / `RESULTS_HOST` / `MODELS_HOST` into the container.
- **sbatch submit** (Alvis): the sbatch resolves `DATA_DIR` /
  `RESULTS_DIR` / `MODELS_DIR` from the submitting shell's environment
  (or its own defaults), creates them if missing, then passes them as
  `--bind` args to `apptainer run`. The same image runs on laptop and
  Alvis; only the bind targets change.

## Design conventions (stable across the library)

- **Container paths are fixed**: `/workspace`, `/data`, `/results`,
  `/models`. Python code never hardcodes host paths.
- **All entrypoints are `pixi run <task>`**: `smoke`, `info`, `test`,
  `lint`. Other templates extend this list (`infer`, `train`, etc.) but
  keep the canonical four.
- **Python code lives under `src/<package>/`**. Scripts under `scripts/`
  are thin wrappers — so the core logic is importable from tests and
  notebooks.
- **Every env var the code reads has a default.** If missing, the code
  uses a sensible fallback or raises early with a clear message.
- **Cephyr = code, Mimer = data.** Every other template in this
  library inherits this split; violating it on Alvis is the number-one
  cause of quota kills.
