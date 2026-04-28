# `07-ollama-cluster-server` — Ollama as a cluster-hosted LLM server

Launches **Ollama** inside an Apptainer SIF on Alvis, exposes its
OpenAI-compatible HTTP endpoint via SSH port-forward, and calls it
from any OpenAI-compatible client.

Use when:

- You want Ollama's simple `pull` / `run` ergonomics.
- Your model is in the Ollama library.
- You need both chat and embeddings endpoints.

## How the pattern works

```
 laptop                                     Alvis compute node
┌──────────────────┐                        ┌───────────────────────────┐
│ openai.OpenAI(   │    SSH -L forward      │ apptainer run ollama.sif  │
│   base_url=      │ <───────────────────── │   ollama serve            │
│     http://local │                        │  (pre-pulls $OLLAMA_MODEL)│
│     host:11434)  │                        │   writes host:port to     │
│                  │                        │     $RESULTS_DIR          │
└──────────────────┘                        └───────────────────────────┘
                                             model cache: Mimer project
```

## Layout diffs vs 02-inference-api-token

- `apptainer/ollama.def` — installs the Ollama binary.
- `slurm/ollama-server.sbatch` — `ollama serve` in background +
  `ollama pull $OLLAMA_MODEL` + writes host:port file.
- `src/ollama_cluster/client.py` — reads host:port, points an
  OpenAI-compatible client at `http://<host>:<port>/v1`.
- `.env.example` adds `OLLAMA_MODEL`, `OLLAMA_MODELS` (cache path,
  defaults to Mimer project path).

## Quickstart

### On cluster (Alvis)

```bash
# 1. sync code + build the SIF (once)
bash _shared/scripts/sync-to-cephyr.sh
ssh <cid>@alvis2.c3se.chalmers.se
cd /cephyr/users/<cid>/Alvis/07-ollama-cluster-server
apptainer build ollama.sif apptainer/ollama.def

# 2. launch the server job (will pre-pull the model if not cached)
sbatch slurm/ollama-server.sbatch
squeue -u $USER                            # wait for R state

# 3. forward the port to laptop
JOBID=<from squeue>
bash _shared/scripts/port-forward.sh $JOBID

# 4. from laptop, call the server
export OPENAI_API_KEY=ollama                # Ollama ignores the key
export OPENAI_BASE_URL=http://localhost:11434/v1
pixi run infer --prompt "Hello" --model llama3.1:8b
```

### Locally (no cluster)

**PowerShell:**

```powershell
# Ollama already installed on laptop with a running `ollama serve`
docker compose up -d dev
docker compose exec dev pixi install
$env:OPENAI_BASE_URL="http://host.docker.internal:11434/v1"
docker compose exec dev pixi run infer --prompt "Hello" --model "llama3.1:8b"
```

**bash / zsh:**

```bash
# Ollama already installed on laptop with a running `ollama serve`
docker compose up -d dev
docker compose exec dev pixi install
OPENAI_BASE_URL=http://host.docker.internal:11434/v1 \
    docker compose exec dev pixi run infer --prompt "Hello" --model "llama3.1:8b"
```

## Storage discipline

- **Model cache** (`OLLAMA_MODELS`) goes on Mimer. Set
  `OLLAMA_MODELS=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/ollama/models`
  — each Ollama model is 2–40 GiB across many files.
- **Never** let it default to `~/.ollama/` on Alvis — Cephyr quota
  suicide (file count, not just bytes).
- Pre-pull models on an interactive login session once, reuse the
  cache across jobs.

## When to leave

- Need higher throughput → see the vLLM pattern in
  `11-multi-provider-inference`.
- Want LM Studio instead → `06-lmstudio-cluster-server`.
- Want to bundle custom weights from git → `14-git-model-bundle`.
