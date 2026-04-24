# `02-inference-api-token` — folder layout

```
02-inference-api-token/
├── README.md                   why-this-template + quickstart
├── .env.example                env vars the template reads, with comments
├── .gitignore
├── docker-compose.yml          laptop dev stack
├── pixi.toml                   pixi tasks + deps (includes openai SDK)
├── pyproject.toml              Python packaging + wheel target
├── apptainer/
│   ├── dev.def                 dev SIF (code bind-mounted in) — laptop + Alvis
│   └── app.def                 deployment SIF (code baked in)
├── configs/
│   └── config.toml             layout config (container paths, default model)
├── scripts/                    entrypoints for `pixi run <task>`
│   ├── smoke.py                pixi run smoke   — offline, asserts SDK imports
│   ├── info.py                 pixi run info    — prints resolved env
│   └── infer.py                pixi run infer   — calls the API, saves JSON
├── src/infer_api/
│   ├── __init__.py
│   ├── config.py               central path + provider env resolver
│   └── providers/
│       ├── __init__.py         exposes `predict`
│       └── openai.py           OpenAI-compatible predict(prompt, **kw)
├── slurm/
│   └── infer-cpu.sbatch        CPU-only inference job (network-bound, no GPU)
├── tests/
│   └── test_smoke.py           pytest — config + provider import + error path
└── docs/
    ├── setup.md                first-time setup (laptop + Alvis)
    ├── usage.md                step-by-step golden path
    ├── modification.md         how to adapt to your project
    ├── structure.md            (this file)
    └── troubleshooting.md      known V3SE-specific issues
```

## Key files, one paragraph each

### `apptainer/dev.def` and `apptainer/app.def`

Pixi-based containers, identical shape to `01-foundation`. `dev.def`
installs only system tools (`curl`, `git`, `openssh-client`, `rsync`,
`tini`) and expects the project bind-mounted at `/workspace` at run
time. `app.def` copies `src/` + `scripts/` + `configs/` into
`/workspace` and runs `pixi install` at build time for reproducible
deployment. Neither SIF bakes `.env` — the `OPENAI_API_KEY` is injected
at run time via `--bind ./.env:/workspace/.env` or `env_file` in
Compose.

### `slurm/infer-cpu.sbatch`

30-minute CPU-only job (`--cpus-per-task=2`, `--mem=4G`, no `--gpus`) —
API calls are network-bound, not compute-bound, so there's no reason to
burn GPU hours on them. Sources `.env` (`set -a; . ./.env; set +a`) so
`OPENAI_API_KEY` reaches the container, defaults `RESULTS_DIR` to
`$PWD/results` if unset, then
`apptainer run --bind .:/workspace $SIF pixi run infer --prompt "$PROMPT"`.
`PROMPT` is overridable via `sbatch --export=ALL,PROMPT="..."`. The
`--account=<PROJECT_ID>` placeholder must be replaced before first
submission.

### `src/infer_api/config.py`

Env-var resolver. `data_dir()`, `results_dir()`, `models_dir()` return
container paths (`/data`, `/results`, `/models` by default);
`openai_model()` returns `OPENAI_MODEL` (default `gpt-4o-mini`);
`openai_base_url()` returns `OPENAI_BASE_URL` or `None`. All other code
reads paths **only** from this module — never from `os.environ`
directly.

### `src/infer_api/providers/openai.py`

The one provider. `_client()` raises a clear `RuntimeError` if
`OPENAI_API_KEY` is unset, constructs an `openai.OpenAI` client
(optionally with `base_url` for Azure / LM Studio / vLLM), and
`predict()` calls `client.chat.completions.create(...)` with a single
user message. Return shape is the canonical
`{"text", "raw", "model", "usage"}` dict used across the library — the
tier-2 multi-provider example consumes this exact shape unchanged.

### `scripts/infer.py`

CLI wrapper. Parses `--prompt` / `--prompt-file` (mutually exclusive),
`--model`, `--temperature`, calls `predict()`, writes the response to
`$RESULTS_DIR/responses/<utc-stamp>.json` (prompt + model + text +
usage), and echoes the generated text on stdout. This is the exact
entrypoint the sbatch and docker exec calls hit via `pixi run infer`.

### `scripts/smoke.py` and `scripts/info.py`

`smoke.py` confirms the `openai` SDK imports and config paths resolve,
with no network call — used by `pixi run smoke`. `info.py` dumps the
same fields as JSON to stdout, useful for verifying the container
picked up `.env`.

### `configs/config.toml`

Static layout — container paths + `[provider.openai] default_model`.
Env vars override at runtime; this file is the fallback.

### `docker-compose.yml`

Laptop dev stack. Builds `../../_shared/docker/Dockerfile.dev`,
bind-mounts the project at `/workspace`, maps `$DATA_HOST` → `/data`,
`$RESULTS_HOST` → `/results`, `$MODELS_HOST` → `/models`, keeps a
`pixi_env` named volume, and exposes `$JUPYTER_PORT`. The container
`sleep infinity`s; you enter with `docker compose exec dev bash`
(PowerShell form: identical). `OPENAI_API_KEY` comes from `.env` via
`env_file:`.

### `tests/test_smoke.py`

Three asserts: config defaults are set, the provider module exposes
`predict` and `__all__`, and `predict()` raises a clear error when
`OPENAI_API_KEY` is unset. Runs under `pixi run test` in < 1 s — no
network, no model.

## Storage model — what lives where

This template is the thinnest V3SE example that makes a real external
call. It produces small JSON artefacts, no weights, no datasets — but
it still respects the Cephyr/Mimer split so downstream templates can
inherit the same layout.

| Container path | Host path on laptop              | Host path on Alvis                                | Storage tier                           |
|----------------|----------------------------------|---------------------------------------------------|----------------------------------------|
| `/workspace`   | `.` (project root)               | `/cephyr/users/<cid>/Alvis/<project>/`            | **Cephyr** — code + SIF only           |
| `/data`        | `${DATA_HOST:-../data}`          | `/mimer/NOBACKUP/groups/<naiss-id>/data/`         | **Mimer project** — prompt files, batch inputs |
| `/results`     | `${RESULTS_HOST:-../results}`    | `/mimer/NOBACKUP/groups/<naiss-id>/results/`      | **Mimer project** — `responses/*.json` |
| `/models`      | `${MODELS_HOST:-../models}`      | `/mimer/NOBACKUP/groups/<naiss-id>/models/`       | **Mimer project** — unused here, kept for parity |

The only artefact this template writes is
`$RESULTS_DIR/responses/<utc>.json`. That path lands on **Mimer
project** on Alvis — never on Cephyr. Even with tiny JSONs, routing
results through Cephyr would blow the 60k-file cap under a batch
inference workload.

### Runtime-vs-build resolution

- **Build time** (`apptainer build …`, `docker compose build`): no
  secrets baked. The SIF ships without `OPENAI_API_KEY`.
- **Compose up** (laptop): `docker-compose.yml` `env_file:` reads
  `.env`, `DATA_HOST` / `RESULTS_HOST` / `MODELS_HOST` map into the
  container. `OPENAI_API_KEY` flows through the Compose env.
- **sbatch submit** (Alvis): `infer-cpu.sbatch` sources `.env` before
  exporting `RESULTS_DIR` and invoking Apptainer. `.env` is bind-mounted
  (or picked up from `/workspace/.env` since the project itself is
  bind-mounted). Container paths resolve exactly as on laptop — the
  only change is that `RESULTS_DIR` points into Mimer, not a laptop
  sibling.
- **No `HF_HOME`**: this template never talks to Hugging Face. If you
  add a tokenizer-based provider later, set `HF_HOME` to a Mimer path
  in `.env` — see `03-hf-shared-hub` for the pattern.

## Design invariants

- **One provider, one return shape.** `predict()` returns
  `{text, raw, model, usage}` no matter which backend answers. Tier-2
  `11-multi-provider-inference` lifts this module in unchanged.
- **Secrets via `.env` only.** Never committed, never baked. `.env` is
  git-ignored; `.env.example` documents the contract.
- **Network-bound jobs stay on CPU.** The sbatch requests no GPU. If
  you ever see this job on a T4, it's misconfigured.
- **Cephyr = code, Mimer = results.** Even trivial JSON goes to Mimer
  when running on Alvis.
