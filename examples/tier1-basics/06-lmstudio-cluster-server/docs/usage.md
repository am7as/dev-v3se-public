# Usage — `06-lmstudio-cluster-server` (step-by-step, zero to results)

Launch an LM Studio server on an Alvis GPU node, port-forward its
OpenAI-compatible endpoint to your laptop, call it from any client.

## 0. What you'll end up with

- A running Slurm job on Alvis hosting `lms server` on a GPU node.
- An SSH tunnel from laptop to the compute node.
- `pixi run infer --prompt "…"` on laptop talks to LM Studio on
  cluster, returns generated text.

## 1. Prerequisites

**Laptop**:
- Docker Desktop + git.
- For local-only use (no cluster): LM Studio installed on laptop
  with a model loaded + its server running.

**Cluster**:
- C3SE Alvis allocation.
- Mimer project space for the LM Studio model cache (models are
  5–40 GiB).

## 2. Clone + configure

**PowerShell:**

```powershell
Copy-Item . ..\my-lmstudio -Recurse
cd ..\my-lmstudio
Copy-Item .env.example .env
```

**bash / zsh:**

```bash
cp -r . ../my-lmstudio
cd ../my-lmstudio
cp .env.example .env
```

Edit `.env`:

```ini
LMSTUDIO_MODEL=lmstudio-community/llama-3.1-8b-instruct
LMSTUDIO_CACHE_DIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/lmstudio

CEPHYR_USER=<cid>
CEPHYR_PROJECT_DIR=/cephyr/users/<cid>/Alvis/my-lmstudio
MIMER_GROUP_ROOT=/mimer/NOBACKUP/groups/<naiss-id>
ALVIS_ACCOUNT=<naiss-id>
```

Fix the sbatch account:

```diff
-#SBATCH --account=<PROJECT_ID>
+#SBATCH --account=<naiss-id>
```

## 3. Push code to cluster (git or rsync)

```bash
# git
git init -b main && git add . && git commit -m "initial" && \
  git remote add origin git@github.com:<team>/<project>.git && git push -u origin main

# On cluster
ssh alvis
cd /cephyr/users/<cid>/Alvis
git clone git@github.com:<team>/<project>.git my-lmstudio
cd my-lmstudio
scp <cid>@<laptop>:~/my-lmstudio/.env .
```

## 4. Build the LM Studio SIF

On Alvis login node (bigger network, faster download):

```bash
export APPTAINER_CACHEDIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/apptainer-cache
mkdir -p $APPTAINER_CACHEDIR
apptainer build lmstudio.sif apptainer/lmstudio.def
```

## 5. Launch the server

```bash
mkdir -p $LMSTUDIO_CACHE_DIR
sbatch slurm/lmstudio-server.sbatch
squeue -u $USER                               # wait for R state

# Once R, find the host + port the server bound:
cat results/lmstudio-host.txt                 # e.g. alvis3-12
cat results/lmstudio-port.txt                 # e.g. 28472
```

First submission has to pull the model (10+ GiB): that happens
inside the job as `lms server` starts. Subsequent submissions
reuse the Mimer cache.

## 6. Port-forward to laptop

Open a separate **laptop** terminal:

**PowerShell:**

```powershell
# Read host + port from cluster
$HOST_NAME = ssh alvis cat /cephyr/users/<cid>/Alvis/my-lmstudio/results/lmstudio-host.txt
$PORT = ssh alvis cat /cephyr/users/<cid>/Alvis/my-lmstudio/results/lmstudio-port.txt

# Forward
ssh -L "${PORT}:${HOST_NAME}:${PORT}" "<cid>@alvis2.c3se.chalmers.se"
```

**bash / zsh:**

```bash
HOST=$(ssh alvis cat /cephyr/users/<cid>/Alvis/my-lmstudio/results/lmstudio-host.txt)
PORT=$(ssh alvis cat /cephyr/users/<cid>/Alvis/my-lmstudio/results/lmstudio-port.txt)
ssh -L "${PORT}:${HOST}:${PORT}" "<cid>@alvis2.c3se.chalmers.se"
```

Leave that terminal open — it keeps the tunnel alive.

## 7. Call the server from laptop

Open a third terminal on laptop:

**PowerShell:**

```powershell
$env:OPENAI_BASE_URL="http://localhost:${PORT}/v1"
$env:OPENAI_API_KEY="lm-studio"
docker compose up -d dev
docker compose exec -e OPENAI_BASE_URL -e OPENAI_API_KEY dev pixi run infer --prompt "Explain gravity"
```

**bash / zsh:**

```bash
export OPENAI_BASE_URL="http://localhost:${PORT}/v1"
export OPENAI_API_KEY=lm-studio
docker compose up -d dev
docker compose exec -e OPENAI_BASE_URL -e OPENAI_API_KEY dev pixi run infer --prompt "Explain gravity"
```

Response written to `results/responses/<ts>.json`.

## 8. Local-only variant (no cluster)

If you just want to use laptop LM Studio:

```bash
# Start LM Studio GUI, load a model, start its server on port 1234
# In your laptop terminal:
export OPENAI_BASE_URL="http://host.docker.internal:1234/v1"
export OPENAI_API_KEY=lm-studio
docker compose exec -e OPENAI_BASE_URL -e OPENAI_API_KEY dev pixi run infer --prompt "hi"
```

No cluster, no Slurm.

## 9. Verification

- [ ] `results/lmstudio-host.txt` and `lmstudio-port.txt` exist
      after the job enters R state.
- [ ] `ssh -L` completes without `Address already in use` (port
      collision — change via `OLLAMA_PORT` / pick a different port).
- [ ] `openai` client call from laptop returns non-empty text.
- [ ] `LMSTUDIO_CACHE_DIR` on Mimer grows on first run, stays stable
      afterwards.

## Troubleshooting

- **Tunnel refuses connection** → server isn't ready yet; check
  `squeue` / `cat slurm-*-lmstudio-server-*.out`.
- **`lms: command not found` in logs** → SIF build failed; rerun
  `apptainer build lmstudio.sif apptainer/lmstudio.def` checking for
  errors.
- **Cephyr quota explosion** → you forgot `LMSTUDIO_CACHE_DIR`;
  double-check it points at Mimer.
- **Can't reach `host.docker.internal` on Linux laptop** → use
  `http://localhost:1234/v1` and run without Docker, or add
  `--add-host=host.docker.internal:host-gateway` to docker-compose.
