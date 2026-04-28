# Structure — `09-hf-hub-streaming`

A file-by-file walkthrough of the example. Use this alongside
`usage.md` when you're trying to locate where to make a change.

```
09-hf-hub-streaming/
├── README.md                 # high-level pitch + quickstart
├── pixi.toml                 # conda/pypi deps + pixi tasks
├── pyproject.toml            # package metadata (hatchling)
├── docker-compose.yml        # laptop dev container wiring
├── .env.example              # canonical env var list (copy to .env)
├── .gitignore                # includes .env, .hf-cache, results/
├── configs/
│   └── config.toml           # declarative defaults shadowed by env vars
├── src/
│   └── hf_hub_streaming/
│       ├── __init__.py       # package version
│       ├── config.py         # env-var resolver (paths, HF options)
│       └── model.py          # HF load() + generate(); HF_HOME safety guard
├── scripts/
│   ├── smoke.py              # imports + CUDA probe; no model load
│   ├── info.py               # dump resolved config as JSON
│   └── infer.py              # real generation; writes results/responses/*.json
├── apptainer/
│   ├── dev.def               # minimal SIF: pixi + toolchain, no code baked
│   └── app.def               # heavier SIF: code baked in, runs `pixi run smoke`
├── slurm/
│   └── gpu-t4.sbatch       # T4 GPU job — runs `dev.sif pixi run infer`
├── tests/
│   └── test_smoke.py         # pytest smoke — no model load
└── docs/
    ├── setup.md              # one-off prerequisites
    ├── usage.md              # zero-to-results
    ├── modification.md       # edit points for real projects
    ├── structure.md          # this file
    └── troubleshooting.md    # common failures
```

## Top-level files

### `README.md`

The pitch. Explains when this template is the right choice vs 03
(shared-hub, no download) and 08 (baked SIF, no download). Contains
the comparison matrix you come back to when deciding between the
three HF examples.

### `pixi.toml`

Pixi workspace definition. Dependencies of interest:

- `torch` pinned to `>=2.5` from the CU121 PyTorch index.
- `transformers`, `accelerate`, `sentencepiece` — the minimal set to
  run most CausalLM models from the Hub.

Tasks:

- `smoke` — fast env probe, no model load.
- `info` — resolved config as JSON.
- `infer` — real generation (calls `scripts/infer.py`).
- `test`, `lint` — hygiene.

### `pyproject.toml`

Hatchling build backend pointing at `src/hf_hub_streaming/`. If you
rename the package (see `modification.md` §1), change both this file
and `pixi.toml`.

### `docker-compose.yml`

Single `dev` service built from the shared `_shared/docker/Dockerfile.dev`.
Host bind mounts:

- `.` → `/workspace` (live code).
- `${DATA_HOST:-../data}` → `/data`.
- `${RESULTS_HOST:-../results}` → `/results`.
- `${MODELS_HOST:-../models}` → `/models`.
- Named volume `pixi_env` for `/workspace/.pixi` so you don't
  reinstall deps on every `docker compose up`.

The GPU `deploy.resources.reservations.devices` stanza is commented
out — uncomment on a GPU-enabled Docker host.

### `.env.example`

Canonical env-var list — this is the shape every copy of `.env` must
keep. The comments call out the **HF_HOME placement rule** loud and
clear because it is the one value where a typo destroys your Cephyr
quota.

### `.gitignore`

Covers `.env`, `.hf-cache/`, `results/`, `.pixi/`, `__pycache__/`,
and `*.sif` so you don't accidentally commit weights or secrets.

## `configs/config.toml`

Declarative defaults (paths, default model). At runtime they are
superseded by env vars resolved in `src/hf_hub_streaming/config.py`,
so edit `.env` for per-environment changes; edit `config.toml` only
to change the defaults used when an env var is absent.

## `src/hf_hub_streaming/`

### `__init__.py`

Exposes `__version__`. Keep it thin — all public API lives in
`model.py`.

### `config.py`

One helper per env var: `data_dir()`, `results_dir()`, `models_dir()`,
`hf_model_id()`, `hf_model_snapshot()`, `device()`, `dtype()`,
`max_new_tokens()`. Reading from `os.environ` is centralised here so
every script and test can monkeypatch one place.

### `model.py`

The heart of the template.

- `_check_hf_home()` — **warning baked into every `load()` call**. If
  `HF_HOME` is empty or starts with `$HOME` / `/cephyr/`, it emits a
  `UserWarning`. This is the safety net: even if you forget to export
  `HF_HOME` in the sbatch, the warning appears in the job log and
  points you at the fix before the first 5 GiB downloads into Cephyr.
- `load()` — `@lru_cache(maxsize=1)` so the first call downloads /
  loads, subsequent calls are free.
- `generate()` — returns the canonical
  `{text, model, device, usage}` dict that every C3SE inference
  template uses.

**Do not** edit the contract of `generate()`; other templates
(11-multi-provider-inference) dispatch on this shape.

## `scripts/`

### `smoke.py`

No-model-load env probe. Prints torch version, CUDA availability,
device names, and the resolved config. Runs in seconds. Use as the
first sbatch on a new cluster — if this fails, nothing else will
work.

### `info.py`

Dumps resolved config (including `HF_MODEL`, device, dtype,
max_new_tokens) as JSON. Great for `diff`-ing laptop vs cluster
settings when debugging "works on my laptop".

### `infer.py`

The real work. Takes `--prompt` or `--prompt-file`, calls
`generate()`, writes the result as `results/responses/<timestamp>.json`
and echoes to stdout.

## `apptainer/`

### `dev.def`

Minimal SIF. Base image is `ghcr.io/prefix-dev/pixi:0.48.0-noble`.
Installs `ca-certificates curl git tini`. **No code baked in** — you
bind-mount your repo with `--bind .:/workspace` at run time. This is
what the sbatch uses by default.

### `app.def`

Heavier SIF. Same base but `%files` copies `pixi.toml`, `src/`,
`scripts/`, etc. into the image and runs `pixi install` at build
time. Use this if you want a truly self-contained SIF to archive (the
trade-off: rebuild on every code change).

## `slurm/gpu-t4.sbatch`

Single-GPU T4 job, 30-minute wall-clock, 32 GiB memory. Sources
`.env`, re-exports `HF_HOME` (with a dangerous default of
`$PWD/.hf-cache` under Cephyr — **your `.env` override protects
you**), then runs:

```bash
apptainer run --nv --bind .:/workspace "$SIF" pixi run infer --prompt "$PROMPT"
```

Submit with:

```bash
sbatch --export=ALL,PROMPT="..." slurm/gpu-t4.sbatch
```

## `tests/test_smoke.py`

pytest. Does not load the model — uses `monkeypatch` to check that
env vars override defaults in `config.py`. Run with
`pixi run test`. Keep this green on CI.
