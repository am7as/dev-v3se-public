# `07-ollama-cluster-server` — folder layout

```
07-ollama-cluster-server/
├── README.md                   why-this-template + quickstart
├── .env.example                env vars the template reads, with comments
├── .gitignore
├── docker-compose.yml          laptop dev stack
├── pixi.toml                   pixi tasks + deps
├── pyproject.toml              Python packaging + wheel target
├── apptainer/
│   ├── dev.def                 dev SIF (code bind-mounted in) — laptop + Alvis
│   ├── app.def                 deployment SIF (code baked in)
│   └── ollama.def              SERVER SIF: Ubuntu + Ollama binary
├── configs/
│   └── config.toml             layout config (container paths, default model)
├── scripts/                    entrypoints for `pixi run <task>`
│   ├── smoke.py                pixi run smoke   — offline, asserts SDK imports
│   ├── info.py                 pixi run info    — prints resolved env
│   └── infer.py                pixi run infer   — calls the server, saves JSON
├── slurm/
│   ├── ollama-server.sbatch    SERVER launcher: apptainer exec ollama serve + host:port
│   └── infer-cpu.sbatch        CPU-only client job (network-bound, no GPU)
├── src/ollama_cluster/
│   ├── __init__.py
│   ├── config.py               central path resolver (DATA_DIR, RESULTS_DIR, …)
│   ├── client.py               KEY — reads host:port, builds OpenAI client
│   └── providers/
│       ├── __init__.py         exposes `predict`
│       └── openai.py           OpenAI-compatible predict(prompt, **kw)
├── tests/
│   └── test_smoke.py           pytest — config + provider import + error path
└── docs/
    ├── setup.md                first-time laptop + Alvis setup
    ├── usage.md                zero-to-results step-by-step
    ├── modification.md         (this layer) what to change when you fork
    ├── structure.md            (this file)
    └── troubleshooting.md      common failures + fixes
```

## Key files, one paragraph each

### `apptainer/ollama.def`

The server SIF. Ubuntu 24.04 base; installs `curl` + `ca-certificates`
and runs the upstream installer
`curl -fsSL https://ollama.com/install.sh | sh`, which drops the
`ollama` binary at `/usr/local/bin/ollama`. Default env sets
`OLLAMA_MODELS=/tmp/ollama-models` and `OLLAMA_HOST=0.0.0.0:11434`;
the sbatch overrides both at run time. The runscript is `exec ollama
"$@"`, so `apptainer run --nv ollama.sif serve` launches the
OpenAI-compatible endpoint.

### `apptainer/dev.def` and `apptainer/app.def`

Pixi-based dev containers for the *client*. `dev.def` bind-mounts the
project dir at `/workspace`; `app.def` copies the code in and runs
`pixi install` at build time for reproducible deployment. Neither
installs Ollama — they only talk to the server over HTTP.

### `slurm/ollama-server.sbatch`

The launcher. Reads `.env`, sets `OLLAMA_MODELS` to a Mimer path,
picks `$OLLAMA_PORT` (default `11434`), writes `$HOST` and `$PORT`
to `results/ollama-{host,port}.txt`, then `apptainer exec --nv` the
server SIF with a compound command: `ollama serve &` → `sleep 5` →
`ollama pull $OLLAMA_MODEL` → `wait` for the server. The pull is
a no-op if the blobs are already in `$OLLAMA_MODELS`. The bind
`$OLLAMA_MODELS:/tmp/ollama-models` is what keeps the model blobs on
Mimer instead of Cephyr. Defaults: 4 h, T4:1, 32 G RAM —
all tunable per section 5 of [modification.md](modification.md).

### `slurm/infer-cpu.sbatch`

Optional companion job: runs the dev SIF's `pixi run infer` on two
CPUs with 4 G RAM. Useful when you want the client also on the
cluster (so no SSH tunnel needed) — set
`OPENAI_BASE_URL=http://<server-node>:<port>/v1` inside the job.

### `src/ollama_cluster/client.py`

The bridging code. `_read_endpoint()` reads
`$RESULTS_DIR/ollama-{host,port}.txt`; `make_client()` resolves a
`base_url` via three-step priority — explicit arg → `OPENAI_BASE_URL`
env → host:port file — and returns an `openai.OpenAI` pointed at the
server. `predict()` wraps `client.chat.completions.create(...)` and
returns the canonical `{text, raw, model, usage}` dict used across the
library. The default `OLLAMA_MODEL` fallback is `llama3.1:8b`.

### `src/ollama_cluster/providers/openai.py`

A second entry to the same API, driven by `config.py` env lookups
rather than by `make_client()` host:port files. Used by the
`ollama_cluster.providers.predict` convenience import; raises a
useful error when `OPENAI_API_KEY` is unset (Ollama accepts any
non-empty string, but the OpenAI SDK demands the header).

### `src/ollama_cluster/config.py`

Env-var resolver. `data_dir()`, `results_dir()`, `models_dir()` return
container paths (`/data`, `/results`, `/models`); `openai_model()` and
`openai_base_url()` surface the relevant env. All other code reads
paths *only* from this module.

### `scripts/infer.py`

CLI wrapper. Parses `--prompt` / `--prompt-file`, `--model`,
`--temperature`, calls `predict()`, writes the response to
`$RESULTS_DIR/responses/<utc-stamp>.json`, and echoes the generated
text on stdout. This is the exact entrypoint the sbatch and docker
exec calls hit via `pixi run infer`.

### `scripts/smoke.py` and `scripts/info.py`

`smoke.py` prints resolved config + confirms the `openai` SDK imports,
with no network call — used by `pixi run smoke`. `info.py` dumps the
same fields as JSON to stdout, useful for verifying the container
picked up `.env`.

### `configs/config.toml`

Static layout — container paths + default model name. Env vars
override at runtime; this file is the fallback.

### `docker-compose.yml`

Laptop dev stack. Builds the shared `Dockerfile.dev` from
`../../_shared/docker/`, bind-mounts the project at `/workspace`, maps
`$DATA_HOST` → `/data`, `$RESULTS_HOST` → `/results`, `$MODELS_HOST`
→ `/models`, and keeps a `pixi_env` named volume so `pixi install`
doesn't re-download on every rebuild. The container `sleep infinity`s;
you enter with `docker compose exec dev bash`.

### `tests/test_smoke.py`

Three asserts: config defaults are set, the provider module exposes
`predict` and `__all__`, and `predict()` raises a clear error when
`OPENAI_API_KEY` is unset. Runs under `pixi run test` in < 1 s.

## Design invariants

- **Three SIFs, three roles.** `ollama.sif` = server binary;
  `dev.sif` = client dev loop; `app.sif` = frozen client for
  deployment. They never merge.
- **host:port files are the handshake.** The server writes two tiny
  text files in `$RESULTS_DIR`; the client reads them. No service
  registry, no shared DB.
- **Code lives on Cephyr, models live on Mimer.** Ollama's default
  `~/.ollama/models` would be a Cephyr quota disaster — that's why
  `OLLAMA_MODELS` is a hard `.env` field, not a default.
- **The laptop and the cluster client are identical code.** Same
  `client.py`, same `predict()`, same `pixi run infer` — only
  `OPENAI_BASE_URL` changes.
