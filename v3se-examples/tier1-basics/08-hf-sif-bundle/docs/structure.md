# Structure — `08-hf-sif-bundle`

A folder-by-folder tour. If you only read four files, read them in
this order:

1. `apptainer/model.def` — where the magic happens. The `%post`
   section downloads the HF weights at build time and bakes them
   into `/opt/model` inside the SIF.
2. `scripts/build-model-sif.sh` — thin wrapper that reads `.env` and
   calls `apptainer build --build-arg`.
3. `src/hf_sif_bundle/model.py` — loads from `/opt/model` with
   `local_files_only=True`, no Hub access.
4. `slurm/gpu-t4.sbatch` — runs the baked SIF on an Alvis T4.

## Top-level

```
08-hf-sif-bundle/
├── README.md            one-screen summary
├── pixi.toml            deps + pixi tasks (smoke / info / infer / test / lint)
├── pyproject.toml       hatchling build for the src/ package
├── docker-compose.yml   laptop dev container (not the model SIF)
├── .env.example         env-var contract (copy to .env)
├── .gitignore           keeps .env, *.sif, results/, .pixi/ out of git
├── apptainer/           Apptainer definitions (dev / app / model)
├── configs/             static config.toml
├── docs/                these docs
├── scripts/             CLI entrypoints + build helper
├── slurm/               Alvis sbatch scripts
├── src/hf_sif_bundle/   the Python package
└── tests/               pytest smoke
```

## `apptainer/`

Three definition files for three different SIFs. They compose — you
almost always want `model.sif` for production.

| File | Produces | Base image | Bakes code? | Bakes weights? | Typical use |
|------|----------|------------|-------------|----------------|-------------|
| `dev.def`   | `dev.sif`   | `ghcr.io/prefix-dev/pixi:0.36.0-noble` | no — bind at runtime | no | local iteration |
| `app.def`   | `app.sif`   | `ghcr.io/prefix-dev/pixi:0.36.0-noble` | yes (`src/`, `scripts/`, etc.) | no | reproducible code, bind weights at runtime |
| `model.def` | `model.sif` | `nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04` | no (code via `pip install transformers`) | **yes** (`/opt/model`) | primary deliverable |

`model.def` highlights:

- `%arguments` declares `HF_MODEL` and `HF_TOKEN` as build-args,
  with `HF_MODEL` defaulting to `google/gemma-2-2b-it`.
- `%post` installs `torch`, `transformers`, `accelerate`, and
  `huggingface_hub`, then runs `huggingface-cli download` into
  `/opt/model`. Writes `/opt/model-metadata.txt` for post-hoc
  provenance.
- `%environment` sets `MODEL_DIR=/opt/model` and `HF_HUB_OFFLINE=1`
  / `TRANSFORMERS_OFFLINE=1` to forbid any accidental Hub calls at
  run time.
- `%runscript` runs a one-liner generate: `model.sif "your prompt"`.

## `configs/`

`config.toml` holds static defaults:

```toml
[paths]
data_dir    = "/data"
results_dir = "/results"
models_dir  = "/models"

[hf]
default_model   = "google/gemma-2-2b-it"
hf_home_default = "/workspace/.hf-cache"
```

Rarely edited per-run — env-vars from `.env` override everything
here.

## `docs/`

| File | Scope |
|------|-------|
| `setup.md` | first-time prerequisites, Apptainer install matrix, cache placement |
| `usage.md` | zero-to-results walkthrough (build + run) |
| `modification.md` | 8-step checklist for making it yours |
| `structure.md` | this file |
| `troubleshooting.md` | common build/run failures + fixes |

## `scripts/`

| File | Purpose |
|------|---------|
| `build-model-sif.sh` | reads `HF_MODEL` / `HF_TOKEN` from `.env`, calls `apptainer build --build-arg`. Output: `./model.sif` (or `$1`). Printed summary at end. |
| `info.py`             | dumps resolved config as JSON. No model load. |
| `smoke.py`            | checks torch + CUDA + transformers, writes `$RESULTS_DIR/smoke.json`. No model load. |
| `infer.py`            | CLI: `pixi run infer --prompt "..."`. Loads the model once (cached), generates, writes `$RESULTS_DIR/responses/<ts>.json`. |

`infer.py` takes `--prompt` or `--prompt-file` (mutually exclusive)
plus optional `--max-new-tokens`.

## `slurm/`

| File | GPU | Walltime | Notes |
|------|-----|----------|-------|
| `gpu-t4.sbatch` | `T4:1` | `0-00:30:00` | Sources `.env`, checks `./dev.sif` exists, runs `apptainer run --nv --bind .:/workspace "$SIF" pixi run infer --prompt "$PROMPT"`. |

Note: the stock sbatch points at `SIF=./dev.sif` for a bind-mounted
development flow. For the production "just run model.sif" path,
override:

```bash
sbatch --export=ALL,SIF=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/sifs/model.sif,PROMPT="Hello" slurm/gpu-t4.sbatch
```

Or copy `gpu-t4.sbatch` to `infer-model-sif-t4.sbatch` and hard-code
the `model.sif` path + the `%runscript` one-liner call (no pixi needed
since `model.def` has its own `%runscript`).

`--account=<PROJECT_ID>` must be replaced before first submission.

## `src/hf_sif_bundle/`

| File | Contents |
|------|----------|
| `__init__.py` | version string |
| `config.py`   | `data_dir()`, `results_dir()`, `hf_model_id()`, `hf_model_snapshot()`, `device()`, `dtype()`, `max_new_tokens()` — all env-driven with defaults |
| `model.py`    | `_resolve_source()` requires `MODEL_DIR` to exist (defaults to `/opt/model`). `load()` is `@lru_cache(maxsize=1)`. `generate()` returns the standard `{text, model, device, usage}` dict. |

Key invariants:

- `MODEL_DIR` defaults to `/opt/model` (the baked path inside the SIF).
  It's also overridable via env — handy for local dev against a
  manually-downloaded directory.
- `local_files_only=True` on both `AutoTokenizer.from_pretrained` and
  `AutoModelForCausalLM.from_pretrained`. This is what makes the
  offline guarantee real.

## `tests/`

`test_smoke.py` — 3 tests, <1 s, no model load. Verifies `config`
reads env correctly. Run with `pixi run test`.

## `docker-compose.yml`

Laptop dev only. Builds from `_shared/docker/Dockerfile.dev`,
bind-mounts the repo at `/workspace`, loads `.env`, sleeps. Useful
for iterating on `scripts/` without rebuilding a SIF every time.
**Not** the production deliverable — that's `model.sif`.

## Artefact flow at a glance

```
.env (HF_MODEL, HF_TOKEN)
   │
   ▼
scripts/build-model-sif.sh
   │
   ▼
apptainer build --build-arg HF_MODEL=… apptainer/model.def
   │                                        │
   │                                        ▼
   │                                   huggingface-cli download
   │                                        │
   ▼                                        ▼
model.sif  ◀─── /opt/model (weights) ───── %post
   │
   ▼
apptainer run --nv model.sif "prompt"   ────▶   generated text
```

## What's NOT here

- No bind-mount of `/mimer/NOBACKUP/Datasets/LLM/huggingface/hub/`
  at run time — that's the defining move of
  `../03-hf-shared-hub/`. This example deliberately carries weights
  inside the SIF.
- No hub streaming at run time (`HF_HUB_OFFLINE=1` enforced). For
  streaming, see `../09-hf-hub-streaming/`.
- No batch inference scaffold — add via `modification.md` §6.
