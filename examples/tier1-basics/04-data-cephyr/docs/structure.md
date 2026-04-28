# `04-data-cephyr` — folder layout

```
04-data-cephyr/
├── README.md                   why-this-template + quickstart
├── .env.example                env vars the template reads, with comments
├── .gitignore
├── docker-compose.yml          laptop dev stack
├── pixi.toml                   pixi tasks + deps (adds pandas)
├── pyproject.toml              Python packaging + wheel target
├── apptainer/
│   ├── dev.def                 dev SIF (code bind-mounted in) — laptop + Alvis
│   └── app.def                 deployment SIF (code baked in)
├── configs/
│   └── datasets.toml           logical dataset registry (sample / private / shared)
├── data/
│   └── sample/                 3 tiny CSVs shipped with the template
│       ├── events.csv
│       ├── measurements.csv
│       └── stations.csv
├── scripts/                    entrypoints for `pixi run <task>`
│   ├── smoke.py                pixi run smoke   — offline, asserts pandas imports
│   ├── info.py                 pixi run info    — prints resolved env
│   └── process.py              pixi run process — reads CSVs, writes summary JSON
├── src/data_cephyr/
│   ├── __init__.py
│   ├── config.py               central path + DATASET resolver
│   └── processing.py           stateless ETL: list_csvs + summarize + write
├── slurm/
│   └── process-cpu.sbatch      CPU-only ETL job (no GPU, 1 h / 16 G)
├── tests/
│   └── test_smoke.py           pytest — config + pandas import + sample processing
└── docs/
    ├── setup.md                first-time setup (laptop + Alvis)
    ├── usage.md                step-by-step golden path
    ├── modification.md         how to adapt to your project
    ├── structure.md            (this file)
    └── troubleshooting.md      known C3SE-specific issues
```

## Key files, one paragraph each

### `data/sample/` (shipped-in-repo)

Three tiny CSVs (events, measurements, stations) totalling a few KB.
They exist so `pixi run process --source sample` works immediately after
clone, on any platform, without binding any external path. **This is
the only `data/` subdir that ships in-repo** — real datasets should be
bind-mounted at `/data` from Mimer (see the storage-model section
below).

### `apptainer/dev.def` and `apptainer/app.def`

Pixi-based containers, identical shape to `01-foundation`. `dev.def`
installs system tools + expects the project bind-mounted at `/workspace`.
`app.def` copies `src/` + `scripts/` + `configs/` + the tiny
`data/sample/` into `/workspace` and runs `pixi install` at build time.
**Real datasets are never baked into the SIF** — they come in via
`--bind <host-path>:/data[:ro]` at run time.

### `slurm/process-cpu.sbatch`

1-hour CPU-only job (`--cpus-per-task=4`, `--mem=16G`, no `--gpus`) —
ETL is I/O-bound, not GPU-bound. Sources `.env`, defaults `RESULTS_DIR`
to `$PWD/results`, then `apptainer run --bind .:/workspace $SIF pixi
run process --source sample`. The sbatch has **three commented-out bind
patterns** (sample / private-Cephyr / shared-Mimer) for copy-paste —
the active line is the sample path, so the job runs on fresh clone.
`--account=<PROJECT_ID>` placeholder must be replaced before first
submission.

### `src/data_cephyr/config.py`

Env-var resolver. `data_dir()`, `results_dir()`, `dataset()` return
container paths and the logical dataset name from `DATASET` env
(default `sample`). Matches the pattern used across the library.

### `src/data_cephyr/processing.py`

Stateless ETL. `list_csvs(root)` rglobs for CSVs, `summarize_dataframe`
computes row / col counts, min/max/mean for numeric columns, null
counts per column. `process(source_dir, out_path)` ties them together
and writes a single JSON summary. Raises `FileNotFoundError` if no CSVs
are found — the classic "`DATA_DIR` is not bind-mounted" signal.

### `scripts/process.py`

CLI. Parses `--source` (falls back to `DATASET` env, then `sample`) and
`--out` (default `summary.json` under `$RESULTS_DIR`). Resolves
`$DATA_DIR / <source>`; if that subdir doesn't exist, falls back to
`$DATA_DIR` itself — so a raw `--bind …:/data` in the sbatch Just
Works without a matching subdir.

### `scripts/smoke.py` and `scripts/info.py`

`smoke.py` confirms `pandas` imports and `summarize_dataframe` on a
tiny in-memory frame works — no file I/O. `info.py` dumps resolved env.

### `configs/datasets.toml`

Logical dataset registry. `[sample]` → `subdir = "sample"`;
`[private]` → `subdir = "."` (use `$DATA_DIR` root as-is, because the
private Cephyr path is bind-mounted directly at `/data`); `[shared]` →
same trick for Mimer read-only mirrors.

### `docker-compose.yml`

Laptop dev stack. Builds `../../_shared/docker/Dockerfile.dev`,
bind-mounts the project at `/workspace`. **One intentional deviation
from the library default**: `${DATA_HOST:-./data}` defaults to the
in-repo `./data` directory (not `../data`) so the sample CSVs are
visible without extra setup. `$RESULTS_HOST` and `$MODELS_HOST` still
default to siblings.

### `tests/test_smoke.py`

Three asserts: config resolution, the `processing.summarize_dataframe`
path on an in-memory frame, and the end-to-end `process()` call on the
shipped `data/sample/` CSVs. Runs under `pixi run test` in < 1 s.

## Storage model — three data sources, three bind patterns

This template's teaching point: `/data` is **not** a fixed host path.
It's a container mount that you aim at different hosts per run. The
three canonical sources map cleanly onto the Cephyr/Mimer split:

| Source logical name | Container path | Alvis host path                                     | Storage tier | Size assumption |
|---------------------|----------------|-----------------------------------------------------|--------------|-----------------|
| `sample`            | `/data/sample` | `/cephyr/users/<cid>/Alvis/<project>/data/sample`   | **Cephyr** (in-repo) | KB — ships with code |
| `private`           | `/data`        | `/mimer/NOBACKUP/groups/<naiss-id>/data/`           | **Mimer project**    | GB–TB — your own raw data |
| `shared`            | `/data` (ro)   | `/mimer/NOBACKUP/Datasets/<dataset>/`               | **Mimer shared**     | large read-only mirrors |

The `private` row is where the post-split model departs from the
template's original name. **"Data on Cephyr" is a misnomer now** — if
your private dataset is more than a few MB or a few dozen files, it
must live on Mimer project, not on Cephyr. The 30 GiB quota and 60k
file cap on Cephyr make it unsafe for anything beyond the in-repo
sample. The sbatch's `private` bind pattern reflects this: the
commented example in the header uses `/cephyr/users/...` for
historical reasons — in production, replace it with
`/mimer/NOBACKUP/groups/<naiss-id>/data/`.

### `/results` always lives on Mimer

Whatever source you processed, `$RESULTS_DIR` points at
`/mimer/NOBACKUP/groups/<naiss-id>/results/` on Alvis. The ETL writes
`summary.json` there. Never let results default to `$SLURM_SUBMIT_DIR`
when submitting from Cephyr — that's how a single overnight batch
melts the 60k file cap.

### Runtime-vs-build resolution

- **Build time** (`apptainer build …`, `docker compose build`): the
  sample CSVs are copied in (via `app.def %files` or in the bind-mount
  on laptop), since they're small and shipped with the code. No real
  dataset is ever baked.
- **Compose up** (laptop): `./data` → `/data`; laptop `../results` →
  `/results`. The whole ETL runs off the sample out of the box.
- **sbatch submit** (Alvis): the sbatch's `--bind` flags are how you
  switch data sources. Edit the sbatch, don't edit the Python. The
  logical `--source <name>` flag and the physical `--bind <host>:/data`
  are coupled: `private` and `shared` both use `subdir = "."` in
  `datasets.toml` because the bind points directly at the dataset
  root.

## Design invariants

- **`/data` is a mount-point, not a directory.** All three sources
  (sample / private / shared) resolve to the same container path;
  only the host bind changes.
- **Processing code is source-agnostic.** `processing.process()` takes
  a `Path` — it can't tell whether that path is Cephyr, Mimer project,
  or a Mimer read-only mirror. Good: that's exactly the abstraction
  boundary this template teaches.
- **`/results` is always Mimer project on Alvis.** Small JSON is still
  JSON — it accumulates fast under batch workloads.
- **Shared datasets are bind-mounted read-only (`:ro`).** Prevents
  accidental writes into `/mimer/NOBACKUP/Datasets/` — that tree is
  mirrored from upstream and must stay pristine.
