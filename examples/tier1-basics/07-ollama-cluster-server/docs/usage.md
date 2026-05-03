# Usage — `07-ollama-cluster-server` (step-by-step, zero to results)

Launch `ollama serve` on an Alvis GPU node, port-forward its
OpenAI-compatible endpoint to your laptop, call it from any client.
Same shape as `06-lmstudio-cluster-server` with Ollama's pull/serve
ergonomics.

## 0. What you'll end up with

- A running Slurm job on Alvis hosting `ollama serve` on a GPU node.
- An SSH tunnel from laptop to the compute node.
- `pixi run infer --prompt "…" --model llama3.1:8b` on laptop talks
  to Ollama on cluster.

## 1. Prerequisites

**Laptop**: Docker Desktop + git. For local-only use, Ollama
installed.

**Cluster**: C3SE Alvis allocation + Mimer project space for
`OLLAMA_MODELS` (5–40 GiB per model).

## 2. Clone + configure

**PowerShell:**

```powershell
Copy-Item . ..\my-ollama -Recurse
cd ..\my-ollama
Copy-Item .env.example .env
```

**bash / zsh:**

```bash
cp -r . ../my-ollama
cd ../my-ollama
cp .env.example .env
```

Edit `.env`:

```ini
OLLAMA_MODEL=llama3.1:8b
OLLAMA_MODELS=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/ollama/models
OLLAMA_PORT=11434

CEPHYR_USER=<cid>
CEPHYR_PROJECT_DIR=/cephyr/users/<cid>/Alvis/my-ollama
MIMER_GROUP_ROOT=/mimer/NOBACKUP/groups/<naiss-id>
ALVIS_ACCOUNT=<naiss-id>
```

Fix the sbatch account:

```diff
-#SBATCH --account=<PROJECT_ID>
+#SBATCH --account=<naiss-id>
```

## 3. Push code to cluster

```bash
# git path
git init -b main && git add . && git commit -m "initial" && \
  git remote add origin git@github.com:<team>/<project>.git && git push -u origin main

ssh alvis
cd /cephyr/users/<cid>/Alvis
git clone git@github.com:<team>/<project>.git my-ollama
cd my-ollama
scp <cid>@<laptop>:~/my-ollama/.env .
```

## 4. Build the Ollama SIF

```bash
export APPTAINER_CACHEDIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/apptainer-cache
mkdir -p $APPTAINER_CACHEDIR
apptainer build ollama.sif apptainer/ollama.def
```

## 5. Pre-pull the model (optional but recommended)

Pull the model once on the login node so later sbatch starts are
fast:

```bash
mkdir -p $OLLAMA_MODELS
apptainer exec \
    --bind "$OLLAMA_MODELS":/tmp/ollama-models \
    --env OLLAMA_MODELS=/tmp/ollama-models \
    ollama.sif \
    bash -c "ollama serve & sleep 5 && ollama pull $OLLAMA_MODEL && kill %1"
```

Alternatively the sbatch can pull lazily on first run.

## 6. Launch the server

```bash
sbatch slurm/ollama-server.sbatch
squeue -u $USER                               # wait for R

cat results/ollama-host.txt                   # e.g. alvis3-14
cat results/ollama-port.txt                   # e.g. 11434
```

The sbatch also triggers `ollama pull $OLLAMA_MODEL` if not already
cached; watch `slurm-ollama-server-*.out` for "Ollama ready".

## 7. Port-forward to laptop

**PowerShell:**

```powershell
$HOST_NAME = ssh alvis cat /cephyr/users/<cid>/Alvis/my-ollama/results/ollama-host.txt
$PORT = ssh alvis cat /cephyr/users/<cid>/Alvis/my-ollama/results/ollama-port.txt
ssh -L "${PORT}:${HOST_NAME}:${PORT}" "<cid>@alvis2.c3se.chalmers.se"
```

**bash / zsh:**

```bash
HOST=$(ssh alvis cat /cephyr/users/<cid>/Alvis/my-ollama/results/ollama-host.txt)
PORT=$(ssh alvis cat /cephyr/users/<cid>/Alvis/my-ollama/results/ollama-port.txt)
ssh -L "${PORT}:${HOST}:${PORT}" "<cid>@alvis2.c3se.chalmers.se"
```

## 8. Call from laptop

**PowerShell:**

```powershell
$env:OPENAI_BASE_URL="http://localhost:${PORT}/v1"
$env:OPENAI_API_KEY="ollama"
docker compose up -d dev
docker compose exec -e OPENAI_BASE_URL -e OPENAI_API_KEY dev pixi run infer --prompt "Hello" --model llama3.1:8b
```

**bash / zsh:**

```bash
export OPENAI_BASE_URL="http://localhost:${PORT}/v1"
export OPENAI_API_KEY=ollama
docker compose up -d dev
docker compose exec -e OPENAI_BASE_URL -e OPENAI_API_KEY dev pixi run infer --prompt "Hello" --model llama3.1:8b
```

## 9. Local-only variant

```bash
# Start laptop Ollama: `ollama serve` in a terminal, `ollama pull llama3.1:8b` in another
export OPENAI_BASE_URL="http://host.docker.internal:11434/v1"
export OPENAI_API_KEY=ollama
docker compose exec -e OPENAI_BASE_URL -e OPENAI_API_KEY dev pixi run infer --prompt "hi" --model llama3.1:8b
```

## 10. Verification

- [ ] `results/ollama-host.txt` and `ollama-port.txt` written after job R.
- [ ] Job log shows "Ollama ready on port …".
- [ ] `OLLAMA_MODELS` on Mimer grows as expected, stays stable.
- [ ] Client call returns non-empty text.

## Troubleshooting

- **Tunnel hangs** → server might still be pulling the model;
  watch `slurm-ollama-server-*.out`.
- **`ollama: command not found`** in logs → SIF build failed or the
  `ollama.com` installer URL changed; rerun `apptainer build`.
- **Cephyr quota spike** → `OLLAMA_MODELS` not set (defaulted to
  `~/.ollama/`); fix `.env` and resubmit.
- **Port 11434 already in use on laptop** → local Ollama running;
  stop it or pick a different `OLLAMA_PORT` in `.env` and rebuild
  the tunnel.
