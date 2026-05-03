# `11-multi-provider-inference` — folder layout

```
11-multi-provider-inference/
├── README.md                   why-this-template + quickstart
├── .env.example                env vars the template reads (per provider)
├── .gitignore
├── docker-compose.yml          laptop dev stack (with optional Claude CLI binds)
├── pixi.toml                   pixi tasks + deps (openai, google-genai, pyyaml)
├── pyproject.toml              Python packaging + wheel target
├── apptainer/
│   ├── dev.def                 dev SIF (code bind-mounted in) — laptop + Alvis
│   └── app.def                 deployment SIF (code baked in)
├── configs/
│   └── providers.yaml          provider registry — env needed, access way, model list
├── scripts/                    entrypoints for `pixi run <task>`
│   ├── smoke.py                pixi run smoke   — offline, SDK imports
│   ├── info.py                 pixi run info    — prints resolved env
│   └── infer.py                pixi run infer   — --provider X --prompt "…"
├── src/infer_multi/
│   ├── __init__.py
│   ├── config.py               path + DEFAULT_PROVIDER resolver
│   ├── router.py               provider name → `predict()` dispatcher
│   └── providers/
│       ├── __init__.py         registry: get(name), available()
│       ├── openai_api.py       OpenAI / Azure cloud API
│       ├── gemini.py           Google Gemini via the unified `google-genai` SDK
│       ├── claude_cli.py       CLI-subscription flow (`claude --print`)
│       ├── lmstudio.py         LM Studio local server (laptop or Alvis via 06)
│       ├── ollama.py           Ollama local server (laptop or Alvis via 07)
│       └── vllm.py             vLLM OpenAI-compatible server client (reads port file)
├── slurm/
│   ├── infer-cpu.sbatch        CPU-only client job (API-token / CLI paths)
│   ├── gpu-t4.sbatch           T4 client job (vLLM path — needs CUDA to tokenise)
│   └── vllm-server.sbatch      A100 server launcher — writes host/port files
├── tests/
│   └── test_smoke.py           pytest — registry + error paths per provider
└── docs/
    ├── setup.md                first-time setup (laptop + Alvis)
    ├── usage.md                step-by-step per-provider walkthrough
    ├── modification.md         how to adapt (add/remove providers)
    ├── structure.md            (this file)
    └── troubleshooting.md      per-provider failure modes
```

## Key files, one paragraph each

### `apptainer/dev.def` and `apptainer/app.def`

Pixi-based containers. Same shape as `01-foundation` — nothing provider-
specific is baked in. `claude_cli` needs the `claude` npm binary on
PATH; install it in the Dockerfile/def or use the shared
`_shared/docker/Dockerfile.dev` which already does. Credentials are
**always** bind-mounted at run time, never baked.

### `slurm/infer-cpu.sbatch`

30-minute CPU-only client job (`--cpus-per-task=2`, `--mem=8G`). Used
for `openai` and `claude_cli` providers — both are network / subprocess
bound. Sources `.env`, defaults `RESULTS_DIR` to `$PWD/results`, runs
`apptainer run --bind .:/workspace $CLAUDE_BINDS $SIF pixi run infer
--provider $PROVIDER --prompt "$PROMPT"`. The `CLAUDE_BINDS` variable
has a commented template for binding
`/cephyr/users/$USER/.claude` → `/root/.claude` — uncomment when using
the `claude_cli` provider.

### `slurm/gpu-t4.sbatch`

30-minute `T4:1` client job. Used for `vllm` provider (the **client**,
not the server — the server has its own sbatch). The GPU here is for
client-side tokenisation; the actual generation happens on the A100
node running vLLM.

### `slurm/vllm-server.sbatch`

8-hour `A100:1` server. Picks a free TCP port, writes host/port to
`$RESULTS_DIR/vllm-{host,port}.txt`, then
`apptainer run --nv … vllm.sif` (SIF built from
`../../_shared/apptainer/vllm.def` on first run). `HF_HOME` defaults to
`$PWD/.hf-cache` unless set — **on Alvis you must point it at Mimer**,
see the storage section. `--account=<PROJECT_ID>` placeholder must be
replaced.

### `src/infer_multi/config.py`

Env resolver. `default_provider()` returns `DEFAULT_PROVIDER` env
(default `openai`); path helpers match the pattern across the library.

### `src/infer_multi/router.py`

Three-line dispatcher: `predict()` takes `provider=None`, looks up
`providers.get(name).predict(...)`. Provider-specific code lives in
`providers/*.py` — the router is thin on purpose.

### `src/infer_multi/providers/openai_api.py`

OpenAI-compatible predict. Reads `OPENAI_API_KEY` + optional
`OPENAI_BASE_URL`; if `OPENAI_BASE_URL` is set but `OPENAI_API_KEY`
isn't, fills the key with `"not-needed"` (local servers ignore it but
the SDK demands a non-empty string). Returns the canonical
`{text, raw, model, usage}` dict.

### `src/infer_multi/providers/claude_cli.py`

Calls `claude --print --model $CLAUDE_MODEL` as a subprocess with the
prompt on stdin. Raises clear errors if the binary isn't on PATH or
if the process exits non-zero. Returns the same canonical dict shape.
Credentials flow: host `~/.claude` + `~/.claude.json` →
`/root/.claude` + `/root/.claude.json` inside the container, bind-
mounted at docker / apptainer run time.

### `src/infer_multi/providers/vllm.py`

vLLM client. `_read_port()` resolves the server endpoint via three-
step priority: explicit env (`VLLM_HOST` / `VLLM_PORT`) → file env
(`VLLM_PORT_FILE` defaults to `/results/vllm-port.txt`) → laptop
defaults. Uses an `openai.OpenAI` client pointed at
`http://<host>:<port>/v1`. This is how the client and server
rendezvous across two separate Slurm allocations.

### `scripts/infer.py`

CLI. `--provider {openai, claude_cli, vllm}`, `--model` override,
`--prompt` / `--prompt-file`. Writes
`$RESULTS_DIR/responses/<provider>__<utc-stamp>.json` and echoes text.
The per-provider filename prefix makes it easy to A/B compare the
same prompt across backends.

### `configs/providers.yaml`

Registry. Each provider lists `env_required`, `env_optional`,
`access_way` (`api_token` / `cli_subscription` /
`served_openai_compatible`), and `models_suggested`. Not loaded at
runtime — it's documentation for humans + the modification checklist.

### `docker-compose.yml`

Laptop dev stack. Builds `../../_shared/docker/Dockerfile.dev`,
bind-mounts the project, maps `$DATA_HOST` / `$RESULTS_HOST` /
`$MODELS_HOST`. **Two commented-out volumes** for the `claude_cli`
provider — bind `$CLAUDE_HOST_DIR` → `/root/.claude` and
`$CLAUDE_HOST_JSON` → `/root/.claude.json`. Uncomment after filling
the env vars in `.env`.

### `tests/test_smoke.py`

Asserts `providers.available()` is non-empty, router raises on an
unknown provider, and each provider raises a clear error when its
required env is missing. No network, no subprocess, no GPU. < 1 s.

## Storage model — three providers, three footprints

This template's defining feature: provider choice dictates storage
needs. Pick the wrong one and you either waste GPU hours or blow
Cephyr quota.

| Provider     | Compute  | Storage footprint                                         | Where it lives on Alvis |
|--------------|----------|-----------------------------------------------------------|-------------------------|
| `openai`     | CPU      | Tiny — outbound HTTPS to api.openai.com                   | Mimer results only      |
| `claude_cli` | CPU      | `~/.claude` credentials (bind-mounted) + CLI's own cache  | Cephyr creds, Mimer results |
| `vllm`       | GPU (A100) | Model snapshot in `HF_HOME` (10–50 GB, thousands of files) | **Mimer** for `HF_HOME` — never Cephyr |

### Canonical bind mounts

| Container path | Laptop host                      | Alvis host                                        | Storage tier                |
|----------------|----------------------------------|---------------------------------------------------|-----------------------------|
| `/workspace`   | `.`                              | `/cephyr/users/<cid>/Alvis/<project>/`            | **Cephyr** — code + SIFs    |
| `/data`        | `${DATA_HOST:-../data}`          | `/mimer/NOBACKUP/groups/<naiss-id>/data/`         | **Mimer project**           |
| `/results`     | `${RESULTS_HOST:-../results}`    | `/mimer/NOBACKUP/groups/<naiss-id>/results/`      | **Mimer project** — `responses/*.json`, `vllm-{host,port}.txt` |
| `/models`      | `${MODELS_HOST:-../models}`      | `/mimer/NOBACKUP/groups/<naiss-id>/models/`       | **Mimer project**           |
| `/root/.claude` | `$CLAUDE_HOST_DIR` (laptop)     | `/cephyr/users/<cid>/.claude/`                    | **Cephyr** — credentials, kilobytes |
| `$HF_HOME` (vllm) | `$PWD/.hf-cache` (laptop)     | `$MIMER_USER_DIR/.hf-cache`                   | **Mimer project** — vLLM weights |

### Handshake files (vllm only)

The vLLM server writes two tiny text files to `$RESULTS_DIR`:

- `vllm-host.txt` — the compute-node hostname
- `vllm-port.txt` — the TCP port vLLM bound to

The client reads them via `VLLM_HOST_FILE` / `VLLM_PORT_FILE`. Since
`$RESULTS_DIR` is on **Mimer project** and Mimer is visible from every
Alvis compute node, this is the entire rendezvous mechanism. No
service registry, no shared DB.

### Runtime-vs-build resolution

- **Build time** (`apptainer build …`, `docker compose build`): code
  + pixi deps + (for the shared Dockerfile) the `claude` npm binary.
  No secrets, no weights, no host paths.
- **Compose up** (laptop): `.env` drives bind paths and provider env
  vars. `claude_cli` additional binds must be uncommented in
  `docker-compose.yml`.
- **Client sbatch submit** (Alvis): sources `.env`, passes `$CLAUDE_BINDS`
  for the `claude_cli` path, binds the project at `/workspace`.
  `RESULTS_DIR` must resolve to Mimer (set in `.env`) — the default
  `$PWD/results` would land on Cephyr.
- **Server sbatch submit** (Alvis, vllm only): `HF_HOME` goes to
  Mimer; port/host files go to Mimer `$RESULTS_DIR`. Client sbatch on
  a different node reads them back from the same Mimer path.

## Design invariants

- **Every provider returns `{text, raw, model, usage}`.** Downstream
  code is provider-agnostic.
- **Provider choice dictates sbatch choice.** API-token / CLI → CPU
  sbatch. vLLM client → T4 sbatch. vLLM server → A100 sbatch.
- **Credentials via bind-mount, never baked.** True for `.env` (API
  keys), true for `~/.claude`, true for `HF_TOKEN`.
- **vLLM weights live on Mimer.** A 9B-param gguf is too big for
  Cephyr; a 70B-param snapshot would evict itself on extraction.
- **Handshake via files on Mimer.** `vllm-{host,port}.txt` under
  `$RESULTS_DIR` replace any service-discovery infrastructure.
