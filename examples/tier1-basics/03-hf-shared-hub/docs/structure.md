# Structure — `03-hf-shared-hub`

A folder-by-folder tour. If you only read three files, read them in
this order:

1. `src/hf_shared_hub/model.py` — the load-and-generate core.
2. `scripts/infer.py` — the CLI that wraps it.
3. `slurm/gpu-t4.sbatch` — how it runs on Alvis.

## Top-level

```
03-hf-shared-hub/
├── README.md            one-screen summary + layout + quickstart
├── pixi.toml            conda / pip deps + `pixi run <task>` entries
├── pyproject.toml       hatchling build config for the `src/` package
├── docker-compose.yml   laptop dev container (bind-mount only)
├── .env.example         canonical env-var contract (copy to .env)
├── .gitignore           keeps .env, results/, *.sif, .pixi/ out of git
├── apptainer/           Apptainer definitions
├── configs/             static config (config.toml)
├── docs/                these docs
├── scripts/             CLI entrypoints (one per pixi task)
├── slurm/               Alvis sbatch scripts
├── src/hf_shared_hub/   the Python package
└── tests/               pytest smoke tests
```

## `apptainer/`

Two definition files. Both are built with
`apptainer build <out>.sif <path>.def` on Alvis (never on laptop for
this example — the shared-hub path doesn't exist locally).

| File | Purpose |
|------|---------|
| `dev.def` | Base SIF with only Pixi + system tools. You bind-mount the repo at run time (`--bind .:/workspace`) so code edits are live. Use this for iteration. |
| `app.def` | Self-contained SIF that bakes `src/` + `scripts/` + `pixi.toml` into `/workspace` at build time. Use this for reproducible deployment. Model weights are NOT baked — this example always reads them from `/mimer/NOBACKUP/Datasets/LLM/huggingface/hub/`. |

Both SIFs load the model via `HF_MODEL_SNAPSHOT`. Neither is a
model-bundle SIF — that's the job of `../08-hf-sif-bundle/`.

## `configs/`

One file: `config.toml`. Static paths and the default HF model id.
Not normally edited per-run — env-vars in `.env` override everything
here.

```toml
[paths]
data_dir    = "/data"
results_dir = "/results"
models_dir  = "/models"

[hf]
default_model   = "google/gemma-2-2b-it"
hf_home_default = "/workspace/.hf-cache"
```

## `docs/`

| File | Scope |
|------|-------|
| `setup.md` | first-time prerequisites + SSH + Cephyr/Mimer layout |
| `usage.md` | step-by-step walkthrough from clone to retrieved results |
| `modification.md` | the 6-step checklist for making it yours |
| `structure.md` | this file |
| `troubleshooting.md` | common failures + fixes |

## `scripts/`

Each file is a thin CLI wrapper around the package. All three write
JSON to `$RESULTS_DIR` and match the `pixi run <task>` names.

| Script | `pixi run` task | What it does |
|--------|-----------------|--------------|
| `info.py`  | `info`  | dumps resolved config (paths, model id, device) — no model loaded |
| `smoke.py` | `smoke` | prints torch / CUDA / transformers versions + resolved `HF_MODEL_SNAPSHOT`; writes `$RESULTS_DIR/smoke.json` |
| `infer.py` | `infer` | loads the model once, runs `generate(prompt)`, writes `$RESULTS_DIR/responses/<ts>.json` |

`infer.py` takes `--prompt` or `--prompt-file` (mutually exclusive),
plus optional `--max-new-tokens`. It caches the loaded model via
`@lru_cache` so repeat calls from the same process are free.

## `slurm/`

One file in the stock scaffold:

| File | GPU | Walltime | Job name |
|------|-----|----------|----------|
| `gpu-t4.sbatch` | `T4:1` | `0-00:30:00` | `infer-hf` |

It:

1. Sources `.env` (`set -a; . ./.env; set +a`).
2. Defaults `RESULTS_DIR` / `HF_HOME` to repo-relative paths if not set.
3. Expects `./dev.sif` (override via `SIF=...`).
4. Runs `apptainer run --nv --bind .:/workspace "$SIF" pixi run infer --prompt "$PROMPT"`.

`PROMPT` is overridable via `sbatch --export=ALL,PROMPT="..."`. The
`--account=<PROJECT_ID>` placeholder must be replaced before first
submission (see `modification.md` §2).

## `src/hf_shared_hub/`

The package. Three files, none large.

| File | Contents |
|------|----------|
| `__init__.py` | version string only |
| `config.py`   | `data_dir()`, `results_dir()`, `hf_model_id()`, `hf_model_snapshot()`, `device()`, `dtype()`, `max_new_tokens()`. All read from env with defaults. |
| `model.py`    | `_resolve_source()` + `load()` + `generate()`. |

Key invariant in `model.py`: `_resolve_source()` raises
`RuntimeError` if `HF_MODEL_SNAPSHOT` is empty or the path doesn't
exist. There is **no** Hub-streaming fallback — that's the whole
point of this template.

`load()` is decorated with `@lru_cache(maxsize=1)` so a long-running
process (batch inference over a CSV, for instance) pays the load cost
once.

`generate()` returns `{text, model, device, usage}` where `usage` is
`{input_tokens, output_tokens}`. This shape is the contract consumed
by tier-2 multi-provider examples.

## `tests/`

One file: `test_smoke.py`. Intentionally avoids loading the model so
`pytest` stays <1 s. It checks:

- `config.data_dir()` and `config.hf_model_id()` return non-empty.
- Setting `HF_MODEL` via env changes `hf_model_id()`.
- Setting `HF_MODEL_SNAPSHOT` via env populates `hf_model_snapshot()`.

Run with `pixi run test`.

## `docker-compose.yml`

Only used for laptop dev. Builds a Pixi-based image from the shared
`_shared/docker/Dockerfile.dev`, bind-mounts the repo at `/workspace`,
loads `.env`, and sleeps. `docker compose exec dev bash` drops you
into a shell where `pixi run info` and `pixi run smoke` work
identically to the cluster — minus the `/mimer/...` mount, which
doesn't exist on laptop.

## What's NOT here

- No `.hf-cache/` — this example never downloads weights.
- No `model.sif` — weights are read from C3SE's mirror, not baked.
- No `HF_TOKEN` usage — the mirror is read-only and ungated.
- No batch-inference scaffold — see `modification.md` §5 to add one.
