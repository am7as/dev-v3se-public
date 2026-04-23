# `06-lmstudio-cluster-server` — folder layout

```
06-lmstudio-cluster-server/
├── README.md                   why-this-template + quickstart
├── .env.example                env vars the template reads, with comments
├── .gitignore
├── docker-compose.yml          laptop dev stack
├── pixi.toml                   pixi tasks + deps
├── pyproject.toml              Python packaging + wheel target
├── apptainer/
│   ├── dev.def                 dev SIF (code bind-mounted in) — laptop + Alvis
│   ├── app.def                 deployment SIF (code baked in)
│   └── lmstudio.def            SERVER SIF: Ubuntu + LM Studio CLI
├── configs/
│   └── config.toml             layout config (container paths, default model)
├── scripts/                    entrypoints for `pixi run <task>`
│   ├── smoke.py                pixi run smoke   — offline, asserts SDK imports
│   ├── info.py                 pixi run info    — prints resolved env
│   └── infer.py                pixi run infer   — calls the server, saves JSON
├── slurm/
│   ├── lmstudio-server.sbatch  SERVER launcher: apptainer run lmstudio.sif + write host:port
│   └── infer-cpu.sbatch        CPU-only client job (network-bound, no GPU)
├── src/lmstudio_cluster/
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

### `apptainer/lmstudio.def`

The server SIF. Ubuntu 24.04 base; installs `curl` plus the GUI
runtime libs LM Studio's AppImage needs (`libfuse2`, `libglib2.0-0`,
`libnss3`, …), downloads a pinned LM Studio AppImage, extracts it so
it runs without FUSE, and symlinks `/usr/local/bin/lms`. The runscript
is `exec lms "$@"`, so `apptainer run lmstudio.sif server start --port
1234 --host 0.0.0.0` launches the OpenAI-compatible server. The AppImage
URL is pinned to a specific LM Studio version — bump it when upstream
moves.

### `apptainer/dev.def` and `apptainer/app.def`

The Pixi-based dev container used by `scripts/infer.py` — identical
shape to `01-foundation`. `dev.def` bind-mounts the project dir at
`/workspace`; `app.def` copies code + installs pixi deps at build time
for reproducible deployment. Neither installs LM Studio itself — they
talk to the server SIF over HTTP.

### `slurm/lmstudio-server.sbatch`

The launcher. Reads `.env`, picks a random TCP port in the 20000–40000
range, writes `$HOST` to `results/lmstudio-host.txt` and `$PORT` to
`results/lmstudio-port.txt`, then executes `apptainer run --nv
--bind $LMSTUDIO_CACHE_DIR:/tmp/lmstudio lmstudio.sif server start --port
$PORT --host 0.0.0.0`. Binding the Mimer cache over `/tmp/lmstudio` is
what keeps the 10+ GiB model downloads off Cephyr. Defaults: 4 h,
T4:1, 32 G RAM — all tunable per section 4 of
[modification.md](modification.md).

### `slurm/infer-cpu.sbatch`

Optional companion job: runs the dev SIF's `pixi run infer` on two
CPUs with 4 G RAM. Useful if you want the client *also* on the cluster
(so no SSH tunnel needed) — set `OPENAI_BASE_URL=http://<server-node>:<port>/v1`
inside the job. Most users skip this and call the tunnelled endpoint
from the laptop directly.

### `src/lmstudio_cluster/client.py`

The bridging code. `_read_endpoint()` reads
`$RESULTS_DIR/lmstudio-{host,port}.txt`; `make_client()` resolves a
`base_url` via three-step priority — explicit arg → `OPENAI_BASE_URL`
env → host:port file — and returns an `openai.OpenAI` pointed at the
server. `predict()` wraps `client.chat.completions.create(...)` and
returns the canonical `{text, raw, model, usage}` dict used across the
library.

### `src/lmstudio_cluster/providers/openai.py`

A second, config-driven entry to the same API. Used by the
`lmstudio_cluster.providers.predict` convenience import; raises a
useful error if `OPENAI_API_KEY` is unset (LM Studio accepts any
non-empty string, but the SDK demands the header). Kept alongside
`client.py` so downstream multi-provider templates can lift this
module in unchanged.

### `src/lmstudio_cluster/config.py`

Env-var resolver. `data_dir()`, `results_dir()`, `models_dir()` return
container paths (`/data`, `/results`, `/models` by default);
`openai_model()` and `openai_base_url()` surface the relevant env. All
other code reads paths *only* from this module — never from `os.environ`
directly.

### `scripts/infer.py`

CLI wrapper. Parses `--prompt` / `--prompt-file`, `--model`,
`--temperature`, calls `predict()`, writes the response to
`$RESULTS_DIR/responses/<utc-stamp>.json`, and echoes the generated
text on stdout. This is the exact entrypoint the sbatch and docker
exec calls hit via `pixi run infer`.

### `scripts/smoke.py` and `scripts/info.py`

`smoke.py` prints resolved config + confirms the `openai` SDK imports,
with no network call — used by `pixi run smoke` and the cpu-smoke
sbatch. `info.py` just dumps the same fields as JSON to stdout,
handy for verifying a container picked up `.env` correctly.

### `configs/config.toml`

Static layout — container paths + default model name. Overridden by
env vars at runtime; defaults are used when `.env` is missing.

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

- **Three SIFs, three roles.** `lmstudio.sif` = server binary;
  `dev.sif` = client dev loop; `app.sif` = frozen client for
  deployment. They never merge.
- **host:port files are the handshake.** The server writes two tiny
  text files in `$RESULTS_DIR`; the client reads them. No service
  registry, no consul, no shared DB.
- **Code lives on Cephyr, models live on Mimer.** The one violation
  of this rule (letting LM Studio default to `~/.cache`) is the
  number-one cause of Cephyr quota kills — that's why
  `LMSTUDIO_CACHE_DIR` is a hard `.env` field, not a default.
- **The laptop and the cluster client are identical code.** Same
  `client.py`, same `predict()`, same `pixi run infer` — only
  `OPENAI_BASE_URL` changes.
