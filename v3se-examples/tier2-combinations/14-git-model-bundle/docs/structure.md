# Structure — `14-git-model-bundle`

A file-by-file walkthrough. Use this alongside `usage.md` when you're
looking for the file to edit.

```
14-git-model-bundle/
├── README.md                 # high-level pitch + quickstart
├── pixi.toml                 # conda/pypi deps + pixi tasks
├── pyproject.toml            # package metadata (hatchling)
├── docker-compose.yml        # laptop dev container wiring
├── Dockerfile.bundle         # laptop-side bundle image (weights baked in)
├── .env.example              # canonical env var list
├── .gitignore                # ignores .env, *.sif, results/, .pixi/
├── configs/
│   └── config.toml           # declarative defaults shadowed by env vars
├── src/
│   └── infer_git_model/
│       ├── __init__.py       # package version
│       ├── config.py         # env-var resolver
│       └── model.py          # loader targeting /opt/model
├── scripts/
│   ├── build-sif.sh          # wrap `apptainer build --build-arg ...`
│   ├── build-docker.sh       # wrap `docker build --build-arg ...`
│   ├── smoke.py              # env probe; no model load
│   ├── info.py               # dump resolved config as JSON
│   └── infer.py              # real generation
├── apptainer/
│   ├── dev.def               # light SIF: pixi only (for host-bind dev)
│   ├── app.def               # code baked in, still no weights
│   └── bundle.def            # weights baked in via %post git clone
├── slurm/
│   └── gpu-t4.sbatch       # T4 GPU job running bundle.sif
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

The pitch. Explains when this template is the right choice vs
`03-hf-shared-hub` (HF Hub model) and `08-hf-sif-bundle` (HF-bundled
SIF). The key differentiator: model is distributed as **a git repo**,
not a HF repo.

### `pixi.toml`

Same base as 03 / 09 — `torch`, `transformers`, `accelerate`,
`sentencepiece`. The `infer_git_model` package is declared here.
Tasks: `smoke`, `info`, `infer`, `test`, `lint`.

### `pyproject.toml`

Hatchling build backend pointing at `src/infer_git_model/`.

### `docker-compose.yml`

Single `dev` service from the shared `Dockerfile.dev`, same as 03 / 09.
Host-bind mounts `/workspace`, `/data`, `/results`, `/models`. This
container is for code editing only — the `Dockerfile.bundle` image
is what actually bakes and runs the model.

### `Dockerfile.bundle`

Laptop-side equivalent of `apptainer/bundle.def`. Base:
`nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04`. `ARG MODEL_REPO` /
`ARG MODEL_REF` forward from `docker build --build-arg ...`. The
single big `RUN` block:

1. Installs `git`, `git-lfs`, `python3-pip`.
2. `git clone --depth 1 --branch $MODEL_REF $MODEL_REPO /opt/model`.
3. `git lfs pull`.
4. Installs deps (`requirements.txt` or `pyproject.toml` in the
   cloned repo).
5. `rm -rf /opt/model/.git` to shrink the final image.

Set `MODEL_DIR=/opt/model` and `PYTHONPATH=/opt/model` at the end so
`import` works without path munging.

### `.env.example`

Canonical env-var list. The `MODEL_DIR=/opt/model` line is marked
"do not change" because it's load-bearing across `bundle.def`,
`Dockerfile.bundle`, and `src/infer_git_model/model.py`.

### `.gitignore`

Covers `.env`, `bundle.sif`, `.pixi/`, `results/`, `__pycache__/`.
SIFs especially — they can be tens of GiB.

## `configs/config.toml`

Declarative defaults (paths, default model identifier). Superseded at
runtime by env vars via `src/infer_git_model/config.py`. Edit `.env`
for per-env changes, `config.toml` for the shipped-by-default values.

## `src/infer_git_model/`

### `__init__.py`

Exposes `__version__`. All public API lives in `model.py`.

### `config.py`

Helpers: `data_dir()`, `results_dir()`, `hf_model_id()`,
`hf_model_snapshot()`, `device()`, `dtype()`, `max_new_tokens()`.
Same shape as in 03 and 09 so downstream multi-provider templates
can swap backends.

### `model.py`

Loader targeting `/opt/model`. Precedence inside `_resolve_source()`:

1. `HF_MODEL_SNAPSHOT` (env) — used when the bundle exposes a
   subdirectory of `/opt/model`.
2. `HF_MODEL` (env) — fallback, rarely used in this template.

`generate()` returns the canonical
`{text, model, device, usage}` dict.

## `scripts/`

### `build-sif.sh`

Laptop or Alvis wrapper. Sources `.env`, requires `MODEL_REPO`,
defaults `MODEL_REF=main`, runs:

```bash
apptainer build \
    --build-arg MODEL_REPO="$MODEL_REPO" \
    --build-arg MODEL_REF="$MODEL_REF" \
    bundle.sif apptainer/bundle.def
```

Optional first positional arg overrides the output filename.

### `build-docker.sh`

Same pattern for Docker — laptop-only. Outputs an image tagged
`git-model-bundle` by default. Tag override via first positional arg.

### `smoke.py`

Imports torch + transformers, probes CUDA visibility, prints resolved
config. No model load — fast enough for sbatch-free iteration.

### `info.py`

Dumps the resolved config as JSON. Useful for `diff`-ing laptop and
cluster settings.

### `infer.py`

Takes `--prompt` or `--prompt-file`, calls `generate()`, writes
`results/responses/<timestamp>.json` and echoes to stdout. Same
interface as 03 and 09 so batch scripts port across.

## `apptainer/`

### `dev.def`

Minimal SIF — `pixi` + `git` only. For host-bind dev: bind your
repo into `/workspace` and run `pixi run ...` as usual. Does **not**
contain weights.

### `app.def`

Code baked in, `pixi install` run at build time. Still does **not**
contain weights. Useful when you want a fully reproducible
code-only SIF paired with a separate weights SIF bound in at runtime.

### `bundle.def`

**The star of this template.** Key sections:

- `%arguments` — declares `MODEL_REPO` / `MODEL_REF` with placeholder
  defaults (`https://example.invalid/...`). Override via
  `apptainer build --build-arg ...`.
- `%post` — installs `git-lfs`, clones `$MODEL_REPO @ $MODEL_REF`
  into `/opt/model`, pulls LFS, runs `pip install` on
  `requirements.txt` or `pyproject.toml`, then `rm -rf .git` to
  shrink the final SIF.
- `%environment` — sets `MODEL_DIR=/opt/model` and prepends to
  `PYTHONPATH`.
- `%runscript` — defaults to `python3 -m infer_git_model "$@"`.
- `%help` — shows the build-time override pattern, always useful to
  `apptainer inspect --helpfile bundle.sif`.

This is the file most likely to need project-specific tweaks. See
`modification.md` §5.

## `slurm/gpu-t4.sbatch`

Single-T4 job, 30-minute wall-clock, 32 GiB memory. Sources `.env`,
runs:

```bash
apptainer run --nv --bind .:/workspace "$SIF" pixi run infer --prompt "$PROMPT"
```

The default `SIF=./dev.sif` line is the #1 footgun — if you want to
run the bundled weights you must set `SIF=./bundle.sif` (either edit
the sbatch or export before submit):

```bash
sbatch --export=ALL,SIF=./bundle.sif,PROMPT="..." slurm/gpu-t4.sbatch
```

## `tests/test_smoke.py`

pytest. Does not load the model. Monkeypatches env vars to check
that `config.py` reads them correctly. Run with `pixi run test`.
