# `12-multi-source-data` — folder layout

```
12-multi-source-data/
├── README.md                   why-this-template + quickstart
├── .env.example                env vars the template reads, per source
├── .gitignore
├── docker-compose.yml          laptop dev stack
├── pixi.toml                   pixi tasks + deps (pandas, datasets, pyyaml)
├── pyproject.toml              Python packaging + wheel target
├── apptainer/
│   ├── dev.def                 dev SIF (code bind-mounted in) — laptop + Alvis
│   └── app.def                 deployment SIF (code baked in)
├── configs/
│   └── sources.yaml            logical-source registry (5 sources, storage docs)
├── data/
│   └── sample/
│       └── rows.csv            1 tiny CSV for `source=local` out-of-the-box
├── scripts/                    entrypoints for `pixi run <task>`
│   ├── smoke.py                pixi run smoke   — offline, asserts imports
│   ├── info.py                 pixi run info    — prints resolved env
│   └── process.py              pixi run process — summarises any source → JSON
├── src/data_multi/
│   ├── __init__.py
│   ├── config.py               path + DATASET_SOURCE env resolver
│   ├── router.py               (source name, dataset) → readable Path
│   ├── processing.py           pandas + HF summarisers
│   └── sources/
│       ├── __init__.py         registry: get(name), available()
│       ├── local.py            files under /data (laptop or generic bind)
│       ├── cephyr_private.py   /data bind-mounted from Cephyr (tiny only)
│       ├── mimer_shared.py     /data:ro bind-mounted from /mimer/NOBACKUP/Datasets/
│       ├── hf_hub.py           datasets.load_dataset() — cache under $HF_HOME
│       └── gcs.py              rclone mount at /tmp/gcs-mount (on-demand)
├── slurm/
│   ├── process-local.sbatch         uses shipped sample under ./data
│   ├── process-private.sbatch       binds a private Cephyr path to /data
│   └── process-mimer-shared.sbatch  binds a /mimer shared dataset to /data:ro
├── tests/
│   └── test_smoke.py           pytest — config + source registry + resolvers
└── docs/
    ├── setup.md                first-time setup (laptop + Alvis)
    ├── usage.md                per-source walkthroughs
    ├── modification.md         how to add a new source
    ├── structure.md            (this file)
    └── troubleshooting.md      per-source failure modes
```

## Key files, one paragraph each

### `data/sample/rows.csv` (shipped-in-repo)

One tiny CSV so `pixi run process --source local --dataset sample`
works on a fresh clone. The only data that ships with the code —
everything else comes in via bind mount, HF download, or rclone.

### `apptainer/dev.def` and `apptainer/app.def`

Pixi-based containers, identical shape to `01-foundation`. `app.def`
copies the tiny `data/sample/` in; real datasets are never baked.
`rclone` lives in the shared Dockerfile/def for the `gcs` source.

### `slurm/process-local.sbatch`

1-hour CPU-only. Runs against the in-repo sample — the "does my SIF
work at all" sanity check. Writes `summary.json` to `$RESULTS_DIR`.

### `slurm/process-private.sbatch`

1-hour CPU-only. `PRIVATE="${PRIVATE_PATH:-/cephyr/users/$USER/Alvis/my-data}"`
plus `--bind "$PRIVATE":/data`. **The default path is a historical
holdover** — for real work, set `PRIVATE_PATH` in `.env` to a Mimer
project path (`/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-data`), not
Cephyr. Cephyr is only safe for tiny config blobs (see storage section).

### `slurm/process-mimer-shared.sbatch`

1-hour CPU-only. `SHARED="${SHARED_PATH:-/mimer/NOBACKUP/Datasets/ImageNet}"`
plus `--bind "$SHARED":/data:ro`. The `:ro` is load-bearing — it's
what protects the shared mirror from accidental writes. Override
`SHARED_PATH` per dataset (`nuScenes`, `waymo`, etc.).

### `src/data_multi/config.py`

Env resolver. `source()` returns `DATASET_SOURCE` (default `local`).
No per-source env vars here — those live in each source module.

### `src/data_multi/router.py`

Two-line dispatcher: `resolve(source, dataset)` → source module's
`resolve(dataset)` which returns a `Path`. Used by the three file-
based sources (local / cephyr_private / mimer_shared). `hf_hub` and
`gcs` each expose their own extra entry (`load()`, `mount()`).

### `src/data_multi/processing.py`

`summarize_csvs(root)` rglobs CSVs, reads with pandas, returns
`{file_count, total_rows, per-file {rows, cols}}`. `summarize_hf_dataset(ds)`
takes a `datasets.Dataset` and returns `{rows, columns, example}`.
`write_summary(summary, out_path)` dumps to JSON.

### `src/data_multi/sources/local.py`

Baseline: `root = config.data_dir()`, returns `root / dataset` if
given else `root`.

### `src/data_multi/sources/cephyr_private.py`

Intentionally identical to `local.py` — the bind in the sbatch does
the work, Python can't tell a Cephyr path from a Mimer path once
mounted at `/data`. Lives as a separate module so the sbatch has
something to name and so the modification checklist has a place to
document Cephyr size limits.

### `src/data_multi/sources/mimer_shared.py`

Also identical to `local.py` by design. The `:ro` on the sbatch bind
is what makes it shared-safe; Python is oblivious.

### `src/data_multi/sources/hf_hub.py`

`resolve(dataset)` returns `$HF_HOME/datasets/` as a pointer (not the
download — HF's internal layout is opaque). `load(dataset, split)`
does the actual `datasets.load_dataset(...)` with `HF_TOKEN` support.
Results of the download land under `$HF_HOME`.

### `src/data_multi/sources/gcs.py`

`resolve(dataset)` returns `/tmp/gcs-mount/<dataset>` (not mounted
yet). `mount()` shells out to `rclone mount --daemon --read-only` with
the `GCS_RCLONE_REMOTE` + `GCS_RCLONE_PATH` env. `unmount()` calls
`fusermount -u`. The mount point is in `/tmp` on purpose — gets blown
away when the Slurm job ends, never pollutes Mimer or Cephyr.

### `scripts/process.py`

CLI. `--source`, `--dataset` (for file-based), `--dataset-id` +
`--split` (for `hf_hub`), `--out` (default `summary.json`). Dispatches
to HF path or file-based path, writes summary JSON to `$RESULTS_DIR`.

### `configs/sources.yaml`

Registry + docs. Each source lists `description` and `examples` with
concrete paths. **This file is the storage-model reference** — it
explicitly calls out Cephyr's 30 GiB / 60k file cap and points users
at `mimer_project` for anything big.

### `docker-compose.yml`

Laptop dev stack. Like `04-data-cephyr`, `$DATA_HOST` defaults to
`./data` (in-repo, so the sample works out of the box). Real datasets
override via `.env`.

### `tests/test_smoke.py`

Asserts source registry is populated, each `resolve()` returns a
`Path`, `processing.summarize_csvs` on an empty dir returns
`file_count=0`. No network, no GPU. < 1 s.

## Storage model — five sources, three tiers

Where each source lands on the Cephyr/Mimer split:

| Source           | Alvis host path                                              | Storage tier          | Writable? | Size budget           |
|------------------|--------------------------------------------------------------|------------------------|-----------|-----------------------|
| `local`          | `/cephyr/users/<cid>/Alvis/<project>/data/` (in-repo sample) | **Cephyr**             | RW        | KB — ships with code  |
| `cephyr_private` | `/cephyr/users/<cid>/Alvis/<arbitrary>/`                     | **Cephyr**             | RW        | ≤ 30 GiB / 60k files  |
| `mimer_project`  | `/mimer/NOBACKUP/groups/<naiss-id>/<cid>/`                   | **Mimer project**      | RW        | hundreds of GiB       |
| `mimer_shared`   | `/mimer/NOBACKUP/Datasets/<dataset>/`                        | **Mimer shared**       | RO        | free (mirrored)       |
| `hf_hub`         | `$HF_HOME` → `$MIMER_USER_DIR/.hf-cache` on Alvis        | **Mimer project**      | RW        | bounded by your quota |
| `gcs`            | `/tmp/gcs-mount` (ephemeral per job)                         | compute-node scratch   | RO        | transient             |

Note: `mimer_project` appears in `configs/sources.yaml` as a logical
name but does **not** have its own Python source module — by design.
From Python it's indistinguishable from `cephyr_private` or
`local` once the sbatch binds it to `/data`. Which sbatch you use and
what you bind is the decision; the code is source-agnostic. Copy
`process-private.sbatch`, rename to `process-mimer-project.sbatch`,
swap `PRIVATE_PATH` for a Mimer path.

### Container-path convention

Same as every template:

| Container path | Laptop host                      | Alvis host (typical)                              | Storage tier                |
|----------------|----------------------------------|---------------------------------------------------|-----------------------------|
| `/workspace`   | `.`                              | `/cephyr/users/<cid>/Alvis/<project>/`            | **Cephyr** — code + SIFs    |
| `/data`        | `${DATA_HOST:-./data}`           | varies per sbatch (see the three sbatches above)  | varies — see table above    |
| `/results`     | `${RESULTS_HOST:-../results}`    | `/mimer/NOBACKUP/groups/<naiss-id>/results/`      | **Mimer project**           |
| `/models`      | `${MODELS_HOST:-../models}`      | `/mimer/NOBACKUP/groups/<naiss-id>/models/`       | **Mimer project**           |
| `$HF_HOME`     | `/workspace/.hf-cache`           | `$MIMER_USER_DIR/.hf-cache`                   | **Mimer project**           |

### Runtime-vs-build resolution

- **Build time**: the tiny `data/sample/rows.csv` is copied into the
  app SIF. No real dataset ever is.
- **Compose up** (laptop): `./data` → `/data`; HF cache in the repo-
  local `.hf-cache/` (git-ignored); `gcs` requires host `rclone.conf`
  + creds bind-mounted into `$HOME/.config/rclone/`.
- **sbatch submit** (Alvis): **the sbatch is where the source
  decision happens**. Choose one of the three sbatches (or clone +
  modify for `mimer_project` / `hf_hub` / `gcs`); edit its bind flag
  to the host path that source expects. `.env` DATASET_SOURCE is a
  default; the sbatch always wins.
- **`HF_HOME` on Alvis**: `.env.example` sets it to
  `/workspace/.hf-cache`, which is safe on laptop but ruinous on
  Alvis. When using `source=hf_hub` on Alvis, add `export
  HF_HOME="$MIMER_USER_DIR/.hf-cache"` to the sbatch (mirror the
  pattern in `05-train-lora/slurm/train-t4.sbatch`).

## Design invariants

- **Python is source-agnostic.** Every file-based source reduces to
  "read `/data`". The decision about where `/data` comes from is in
  the sbatch (and in `docker-compose.yml` on laptop).
- **`/data` is a mount-point, not a directory.** Each sbatch binds a
  different host path to the same container path.
- **Read-only for shared.** `mimer_shared` is bound `:ro`. Never
  write into `/mimer/NOBACKUP/Datasets/`.
- **HF cache = Mimer, not Cephyr, not `$HOME`.** Override `HF_HOME`
  in the sbatch for `hf_hub` runs.
- **`cephyr_private` is a label, not a prescription.** Move anything
  bigger than a few MB to `mimer_project` — the name is kept only
  because the wrapper-template still ships scripts with that label.
