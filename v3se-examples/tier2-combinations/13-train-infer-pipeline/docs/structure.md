# `13-train-infer-pipeline` — folder layout

```
13-train-infer-pipeline/
├── README.md                   why-this-template + quickstart
├── .env.example                env vars + training + tracking config
├── .gitignore
├── docker-compose.yml          laptop dev stack
├── pixi.toml                   pixi tasks + deps (torch, peft, trl, wandb, mlflow)
├── pyproject.toml              Python packaging + wheel target
├── apptainer/
│   ├── dev.def                 dev SIF — used for training + bundling
│   ├── app.def                 deployment SIF (code baked, no weights)
│   └── bundle.def.tpl          TEMPLATE — materialized per-bundle with real adapter path
├── configs/
│   └── config.toml             layout config (container paths)
├── scripts/                    entrypoints for `pixi run <task>`
│   ├── smoke.py                pixi run smoke   — offline, asserts imports
│   ├── info.py                 pixi run info    — prints resolved env
│   ├── train.py                pixi run train   — LoRA finetune → adapter dir
│   ├── bundle.py               pixi run bundle  — adapter → self-contained SIF
│   └── infer.py                pixi run infer   — load base+adapter, generate
├── src/train_infer/
│   ├── __init__.py
│   ├── config.py               path + training-hyperparam env resolver
│   ├── train.py                core: load → LoRA wrap → Trainer → save adapter
│   └── bundler.py              materialises bundle.def.tpl + apptainer build
├── slurm/
│   ├── train-t4.sbatch         1× T4 training job (2 h / 32 G / `--nv`)
│   ├── bundle.sbatch           CPU job — runs `apptainer build` on a compute node
│   └── infer.sbatch            1× T4 — runs a bundled SIF against a prompt
├── tests/
│   └── test_smoke.py           pytest — config + bundler template parsing
└── docs/
    ├── setup.md                first-time setup (laptop + Alvis)
    ├── usage.md                full pipeline walkthrough (train → bundle → infer)
    ├── modification.md         how to adapt to your base model / dataset
    ├── structure.md            (this file)
    └── troubleshooting.md      per-stage failure modes
```

## Key files, one paragraph each

### `apptainer/dev.def` and `apptainer/app.def`

Pixi-based containers — same as `05-train-lora`. `dev.def` is what
`pixi run train` and `pixi run bundle` execute inside. `app.def` is
the reproducible build of the training code itself (rarely used at
inference time, because bundled SIFs are what you actually deploy).

### `apptainer/bundle.def.tpl`

The **template** for bundled inference SIFs. Two string placeholders
(`ADAPTER_SRC`, `BASE_MODEL`) are substituted by `bundler.py` at build
time. The materialized def:

- Copies the training code (`src/`, `scripts/`, `configs/`) into
  `/workspace`.
- Copies the **adapter directory** (MB-scale) to `/opt/adapter`.
- Downloads the **base model** via `huggingface-cli download` at SIF-
  build time, stored in `/opt/base` inside the image.
- Sets `HF_HUB_OFFLINE=1` + `TRANSFORMERS_OFFLINE=1` so inference never
  reaches out to the Hub.
- Runscript: `pixi run infer --adapter-dir /opt/adapter --base-dir /opt/base "$@"`.

Bundled SIFs are GB-scale (base model + adapter + pixi env) and
**self-contained** — no weight download at run time, no internet
needed.

### `slurm/train-t4.sbatch`

2-hour `T4:1` job. Same Cephyr/Mimer branch as `05-train-lora` — if
`MIMER_PROJECT_PATH` is set, `RESULTS_DIR` + `HF_HOME` go to Mimer;
otherwise falls back to `$PWD` with a warning. Writes the adapter to
`$RESULTS_DIR/adapters/<utc-stamp>/`.

### `slurm/bundle.sbatch`

1-hour CPU-only job. Expects `ADAPTER=/path/to/adapter` via
`--export=ALL,ADAPTER=…`. Runs `apptainer run --bind .:/workspace
$SIF pixi run bundle --adapter-dir "$ADAPTER"`, which in turn calls
`apptainer build` inside the container — needs user-namespaces
available on the compute node (Alvis supports this). Output lands at
`$RESULTS_DIR/bundles/<utc-stamp>.sif` plus a `.json` manifest and a
`.def` alongside for auditability.

### `slurm/infer.sbatch`

30-minute `T4:1`. Takes `BUNDLE=/path/to/<ts>.sif` and `PROMPT="…"`
via `--export`. No `dev.sif` needed — the bundle is self-contained.
`apptainer run --nv "$BUNDLE" --prompt "$PROMPT"` — the bundle's
runscript carries everything downstream.

### `src/train_infer/config.py`

Env resolver with the same shape as `05-train-lora/config.py` —
`model_id()`, `model_snapshot()`, `dataset_id()`, LoRA hyperparams.

### `src/train_infer/train.py`

LoRA training loop. Reports to `wandb` if `WANDB_API_KEY` is set, to
`mlflow` if `MLFLOW_TRACKING_URI` is set, neither if both are unset.
Writes adapter + `run_summary.json` to
`$RESULTS_DIR/adapters/<utc-stamp>/`.

### `src/train_infer/bundler.py`

`build(adapter_dir, base_model, out_sif)`:
1. Reads `apptainer/bundle.def.tpl`.
2. String-replaces `ADAPTER_SRC` with the adapter path and
   `BASE_MODEL` with the base model id.
3. Writes the materialised `.def` next to the output SIF.
4. Runs `apptainer build -F out.sif out.def`.
5. Writes a `.json` manifest pointing at both.

Raises `FileNotFoundError` if the template or the adapter directory
is missing — no silent empty bundles.

### `scripts/train.py` / `scripts/bundle.py` / `scripts/infer.py`

Thin CLI wrappers around the three core ops. `train.py` prints the
next-step command (`pixi run bundle --adapter-dir …`) so the pipeline
is self-documenting. `infer.py` resolves the adapter dir from either
`--adapter-dir` or the bundled `BUNDLED_ADAPTER_DIR` env (set by the
bundle's `%environment` block) — same script works inside `dev.sif`
and inside a bundle.

### `configs/config.toml`

Static container-path layout — no training hyperparams (those live in
`.env`).

### `docker-compose.yml`

Laptop dev stack. Identical to `05-train-lora`: bind-mount project,
`$DATA_HOST` / `$RESULTS_HOST` / `$MODELS_HOST`, pixi-env volume.
GPU stanza is commented; uncomment for a Linux host with CUDA.

### `tests/test_smoke.py`

Asserts config defaults, the bundler template is readable, and
`build()` raises clearly on missing inputs. Does **not** train, does
**not** bundle — both need GPU + apptainer. < 1 s.

## Storage model — three artefacts, three sizes

The pipeline produces three artefact classes. Each has a distinct
storage profile:

| Artefact            | Size               | Storage tier       | Lifetime                    |
|---------------------|--------------------|--------------------|-----------------------------|
| Trained adapter     | MB (LoRA weights)  | **Mimer project**  | per-run; keep several        |
| Run summary JSON    | KB                 | **Mimer project**  | per-run                      |
| Bundled SIF         | GB (base + adapter + env) | **Mimer project** | per release; deploy target |
| HF cache (`HF_HOME`)| GB — thousands of files | **Mimer project** | across runs; never Cephyr |
| Bundle `.def`       | KB                 | **Mimer project**  | per bundle; audit trail      |

### Canonical bind mounts

| Container path | Laptop host                      | Alvis host                                        | Storage tier                |
|----------------|----------------------------------|---------------------------------------------------|-----------------------------|
| `/workspace`   | `.`                              | `/cephyr/users/<cid>/Alvis/<project>/`            | **Cephyr** — code + SIFs    |
| `/data`        | `${DATA_HOST:-../data}`          | `/mimer/NOBACKUP/groups/<naiss-id>/data/`         | **Mimer project** — training JSONL |
| `/results`     | `${RESULTS_HOST:-../results}`    | `$MIMER_PROJECT_PATH/results/`                    | **Mimer project** — `adapters/<ts>/`, `bundles/<ts>.sif` |
| `/models`      | `${MODELS_HOST:-../models}`      | `/mimer/NOBACKUP/groups/<naiss-id>/models/`       | **Mimer project**           |
| `$HF_HOME`     | `/workspace/.hf-cache`           | `$MIMER_PROJECT_PATH/.hf-cache`                   | **Mimer project**           |

### Runtime-vs-build resolution

- **Train** (`dev.sif` @ T4): `$HF_HOME` → Mimer. Base model
  downloads once, adapter saves as MB under `$RESULTS_DIR/adapters/`.
- **Bundle** (`dev.sif` @ CPU): reads the adapter from
  `$RESULTS_DIR/adapters/<ts>/` on Mimer, reads the template from
  Cephyr-resident code, writes the new SIF to
  `$RESULTS_DIR/bundles/<ts>.sif` on Mimer. **At SIF-build time,
  `huggingface-cli download` re-downloads the base model into `/opt/base`
  inside the image** — this is intentional: the bundle becomes fully
  offline-usable afterwards. The HF cache on Mimer is a separate copy.
- **Infer** (bundled SIF @ T4): no external storage needed. The SIF
  is on Cephyr (as any SIF), weights + adapter are baked in, only
  `$RESULTS_DIR` is bind-mounted for output artefacts if the runscript
  writes any (default: just stdout).

### Cephyr-vs-Mimer for the bundle SIF

A bundled SIF can be 20–50 GB (a 9B-param base + LoRA adapter + pixi
env). It counts as one file, so it fits the 60k cap trivially — but
the 30 GiB quota on Cephyr means you can **only keep one or two
bundles on Cephyr**. Best practice: keep bundles on Mimer
(`$RESULTS_DIR/bundles/`), symlink the active one to Cephyr if you
need it next to the code, and rsync back to laptop when finalising a
release.

## Design invariants

- **Train produces an adapter, not a model.** Base weights are never
  re-saved. Adapters are the only MB-scale artefact to keep around.
- **Bundle materialises a template.** `bundle.def.tpl` has
  placeholders; the Python bundler substitutes them per-build. Defs
  are written alongside SIFs for audit.
- **Bundles are offline.** `HF_HUB_OFFLINE=1` + `TRANSFORMERS_OFFLINE=1`
  are baked in. A bundle runs in an air-gapped environment.
- **Mimer holds everything heavy.** Adapters, bundles, HF cache, even
  the training checkpoints (if you enable `save_strategy`).
- **The pipeline is three sbatches, one code base.** `pixi run train`
  / `bundle` / `infer` are three tasks in one `pixi.toml`; sbatches
  select which to run.
