# Usage — `09-hf-hub-streaming` (step-by-step, zero to results)

Stream a HuggingFace model from the Hub at first call. Simplest
pattern, perfect for laptop dev and quick cluster jobs.

## 0. What you'll end up with

- Laptop: `docker compose exec dev pixi run infer --prompt "…"`
  generates text after a one-time model download.
- Cluster: `sbatch slurm/gpu-t4.sbatch` downloads (first run) or
  reads-from-Mimer-cache (subsequent runs) and generates.

## 1. Prerequisites

**On laptop**: Docker Desktop (or Docker Engine on Linux), git,
enough disk for the model (5–40 GiB depending on model).

**On cluster**: C3SE Alvis allocation. Mimer project path with
enough free space for the model cache (same 5–40 GiB).

## 2. Clone the template

**PowerShell:**

```powershell
Copy-Item . ..\my-hf-streaming -Recurse
cd ..\my-hf-streaming
```

**bash / zsh:**

```bash
cp -r . ../my-hf-streaming
cd ../my-hf-streaming
```

## 3. Configure `.env`

**PowerShell:**

```powershell
Copy-Item .env.example .env
```

**bash / zsh:**

```bash
cp .env.example .env
```

Edit `.env`:

```ini
HF_MODEL=google/gemma-2-2b-it
HF_TOKEN=                                        # set if model is gated

# Laptop (in-container) cache path
HF_HOME=/workspace/.hf-cache

# C3SE cluster — the important bit
CEPHYR_USER=<your-cid>
CEPHYR_PROJECT_PATH=/cephyr/users/<your-cid>/Alvis/my-hf-streaming
MIMER_GROUP_PATH=/mimer/NOBACKUP/groups/<your-naiss-id>
MIMER_PROJECT_PATH=/mimer/NOBACKUP/groups/<your-naiss-id>/<your-cid>/my-hf-streaming
ALVIS_ACCOUNT=<your-naiss-id>
```

Fix the Slurm account:

```diff
-#SBATCH --account=<PROJECT_ID>
+#SBATCH --account=<your-naiss-id>
```

## 4. Laptop smoke test

```bash
docker compose up -d dev
docker compose exec dev pixi install
docker compose exec dev pixi run smoke
```

Then the real thing (first run downloads the weights into
`/workspace/.hf-cache/`):

```bash
docker compose exec dev pixi run infer --prompt "Explain gravity in 3 sentences."
```

Subsequent calls are ~instant (cache hit). Check disk usage:

```bash
docker compose exec dev du -sh /workspace/.hf-cache/
```

## 5. Push to cluster (git or rsync)

**Option A — git (recommended)**:

```bash
git init -b main
git add .
git commit -m "initial scaffold"
git remote add origin git@github.com:<team>/<project>.git
git push -u origin main

ssh alvis
cd /cephyr/users/<cid>/Alvis
git clone git@github.com:<team>/<project>.git my-hf-streaming
cd my-hf-streaming
scp <cid>@<laptop>:~/my-hf-streaming/.env .
```

**Option B — rsync**:

```bash
bash _shared/scripts/sync-to-cephyr.sh
ssh alvis
cd /cephyr/users/<cid>/Alvis/my-hf-streaming
```

## 6. Configure HF_HOME on the cluster (critical)

Edit `.env` on the cluster side — `HF_HOME` MUST point at Mimer, not
Cephyr:

```ini
# On cluster .env — NOTE: different from laptop .env
HF_HOME=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-hf-streaming/.hf-cache
TRANSFORMERS_CACHE=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-hf-streaming/.hf-cache
```

```bash
mkdir -p /mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-hf-streaming/.hf-cache
```

Verify by sourcing and inspecting:

```bash
set -a; . ./.env; set +a
echo "$HF_HOME"
ls -d "$HF_HOME"
```

## 7. Build the SIF on Alvis

```bash
export APPTAINER_CACHEDIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/apptainer-cache
mkdir -p $APPTAINER_CACHEDIR
apptainer build dev.sif apptainer/dev.def
```

## 8. Cluster smoke test

```bash
sbatch slurm/cpu-smoke.sbatch
squeue -u $USER
cat slurm-*-cpu-smoke-*.out
```

Expected: environment info + `HF_HOME` resolved to a Mimer path. The
`model.py` will warn if `HF_HOME` looks dangerous.

Then GPU smoke (which actually downloads the model on first run):

```bash
sbatch slurm/gpu-t4.sbatch
cat slurm-*-gpu-t4-*.out
```

Expected: `device: cuda`, `gpu: Tesla T4`, weights downloaded to
`$HF_HOME` (watch Mimer usage), and a short generated completion.

Subsequent `gpu-t4` submissions reuse the cache — much faster.

## 9. Run your real prompts

```bash
sbatch --export=ALL,PROMPT="Your question here" slurm/gpu-t4.sbatch
```

For batch, write `scripts/infer_batch.py` same as in 03 and 08; call
`hf_hub_streaming.model.generate(...)`.

## 10. Retrieve results

```bash
rsync -avh --progress \
  <cid>@alvis2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/my-hf-streaming/results/ \
  ./results/
```

## 11. Verification checklist

- [ ] `.env` on cluster has `HF_HOME` pointing at Mimer.
- [ ] `ls /mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-hf-streaming/.hf-cache` exists.
- [ ] `C3SE_quota` after a run shows Cephyr file count unchanged
      (proof that HF cache didn't land on Cephyr).
- [ ] `gpu-t4` log shows successful download on first run, fast load
      on subsequent runs.
- [ ] No `HF_HOME is under Cephyr/home` warning in the log.

## Troubleshooting

- **Cephyr quota warning** right after the first run → `HF_HOME` is
  wrong (likely defaulted to `~/.cache/huggingface/`). Fix
  `.env` AND the sbatch's explicit `export HF_HOME=…` line.
- **"Repository Not Found" / "401"** → gated model; set `HF_TOKEN`
  in `.env` and re-export before `sbatch`.
- **Very slow on every job** → every new compute node starts with a
  cold cache **unless** `HF_HOME` points at the same Mimer path for
  all jobs. With Mimer, only the first cluster-wide run downloads.
- **Want to skip downloads entirely** → you probably want
  `../03-hf-shared-hub/` (if C3SE mirrors the model) or
  `../08-hf-sif-bundle/` (if you can bake a SIF).
