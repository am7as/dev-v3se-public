# `06-lmstudio-cluster-server` — LM Studio as a cluster-hosted LLM server

Launches **LM Studio** inside an Apptainer SIF on Alvis, exposes its
OpenAI-compatible HTTP endpoint via SSH port-forward, and calls it
from any OpenAI-compatible client.

Use when:

- You want a managed UI / model catalog like LM Studio provides.
- Your model is in the LM Studio catalog (GGUF format).
- You don't need the throughput ceiling of vLLM.

## How the pattern works

```
 laptop                                     Alvis compute node
┌──────────────────┐                        ┌───────────────────────────┐
│ openai.OpenAI(   │    SSH -L forward      │ apptainer run lmstudio.sif│
│   base_url=      │ <───────────────────── │   lms server start --port │
│     http://local │                        │  + writes host:port to    │
│     host:8890)   │                        │    $RESULTS_DIR           │
└──────────────────┘                        └───────────────────────────┘
                                             model cache: Mimer project
```

## Layout diffs vs 02-inference-api-token

- `apptainer/lmstudio.def` — installs LM Studio CLI in an Ubuntu base.
- `slurm/lmstudio-server.sbatch` — launches `lms server`, writes
  `$RESULTS_DIR/lmstudio-host.txt` and `$RESULTS_DIR/lmstudio-port.txt`.
- `src/lmstudio_cluster/client.py` — reads host:port, points an
  OpenAI-compatible client at `http://<host>:<port>/v1`.
- `.env.example` adds `LMSTUDIO_MODEL`, `LMSTUDIO_CACHE_DIR`
  (defaults to Mimer project path).

## Quickstart

### On cluster (Alvis)

```bash
# 1. sync code + build the SIF (once)
bash _shared/scripts/sync-to-cephyr.sh
ssh <cid>@alvis2.c3se.chalmers.se
cd /cephyr/users/<cid>/Alvis/06-lmstudio-cluster-server
apptainer build lmstudio.sif apptainer/lmstudio.def

# 2. launch the server job
sbatch slurm/lmstudio-server.sbatch
squeue -u $USER                            # wait for R state

# 3. forward the port to laptop (in a separate laptop terminal)
JOBID=<from squeue>
bash _shared/scripts/port-forward.sh $JOBID
# (reads host:port from the job's $RESULTS_DIR, sets up SSH -L)

# 4. from laptop, call the server
export OPENAI_API_KEY=lm-studio             # LM Studio ignores the key
export OPENAI_BASE_URL=http://localhost:1234/v1
pixi run infer --prompt "Hello" --model <LMSTUDIO_MODEL>
```

### Locally (no cluster)

**PowerShell:**

```powershell
# Install LM Studio on your laptop, load a model, start its server on port 1234
docker compose up -d dev
docker compose exec dev pixi install
$env:OPENAI_BASE_URL="http://host.docker.internal:1234/v1"
docker compose exec dev pixi run infer --prompt "Hello"
```

**bash / zsh:**

```bash
# Install LM Studio on your laptop, load a model, start its server on port 1234
docker compose up -d dev
docker compose exec dev pixi install
OPENAI_BASE_URL=http://host.docker.internal:1234/v1 \
    docker compose exec dev pixi run infer --prompt "Hello"
```

## Storage discipline

- **Model cache** goes on Mimer, NOT Cephyr. Set
  `LMSTUDIO_CACHE_DIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/lmstudio`
  — a single LLM download can be 10+ GiB and 1000s of files.
- **Logs and host:port files** in `$RESULTS_DIR` (Cephyr is fine for
  these — tiny text files).
- **Never** let LM Studio default to `~/.cache/lm-studio/` on Alvis —
  Cephyr quota suicide.

## When to leave

- Need higher throughput → see the vLLM pattern in
  `11-multi-provider-inference`.
- Want Ollama instead → `07-ollama-cluster-server`.
- Want to bundle your own custom weights → `14-git-model-bundle`.
