# Usage — `08-hf-sif-bundle` (step-by-step, zero to results)

Build a self-contained SIF with HuggingFace model weights baked in,
then run it on laptop or cluster.

## 0. What you'll end up with

- A single `model.sif` file (typically 4–30 GiB depending on model
  size) that you can copy anywhere.
- Running `apptainer run --nv model.sif "Hello"` produces generated
  text without any Hub / network access.
- On cluster: `sbatch slurm/gpu-t4.sbatch` runs the same SIF on a T4
  and writes results to `$RESULTS_DIR`.

## 1. Prerequisites

**On laptop** (if building the SIF locally):

- Apptainer installed (Linux native, or WSL2 on Windows, or macFUSE
  + Apptainer on macOS). Docker won't do — SIF needs Apptainer.
- `git` + Python 3 (anything modern).
- Disk space: ≥ 2× the model size (for build cache + output).

**On cluster** (if building on Alvis login node, which is faster for
big models because of the fast network):

- C3SE account with Alvis allocation.
- Enough Mimer project space to host `$APPTAINER_CACHEDIR` during
  the build (the cache can be 2–3× the model size transiently).

## 2. Clone the template

**PowerShell:**

```powershell
Copy-Item . ..\my-hf-bundle -Recurse
cd ..\my-hf-bundle
```

**bash / zsh:**

```bash
cp -r . ../my-hf-bundle
cd ../my-hf-bundle
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
HF_MODEL=google/gemma-2-2b-it       # any public HF repo id
HF_TOKEN=hf_xxx                     # only if the model is gated

CEPHYR_USER=<your-cid>
CEPHYR_PROJECT_PATH=/cephyr/users/<your-cid>/Alvis/my-hf-bundle
MIMER_GROUP_PATH=/mimer/NOBACKUP/groups/<your-naiss-id>
MIMER_PROJECT_PATH=/mimer/NOBACKUP/groups/<your-naiss-id>/<your-cid>/my-hf-bundle
ALVIS_ACCOUNT=<your-naiss-id>
```

Fix the Slurm account in every `slurm/*.sbatch`:

```diff
-#SBATCH --account=<PROJECT_ID>
+#SBATCH --account=<your-naiss-id>
```

## 4. Build the model SIF

### Option A — build on laptop

**PowerShell (inside WSL2) / bash / zsh:**

```bash
# Make sure apptainer is installed:
apptainer --version

# Build. Reads HF_MODEL and HF_TOKEN from .env.
bash scripts/build-model-sif.sh
```

For a 2 GB model this takes ~5–10 minutes (CUDA base pull + `pip
install transformers` + HF download). Output: `./model.sif`.

### Option B — build on Alvis login node (recommended for big models)

```bash
# On laptop: push code (either via git or rsync)
bash _shared/scripts/sync-to-cephyr.sh

ssh alvis
cd /cephyr/users/<cid>/Alvis/my-hf-bundle

# Put your .env on the cluster (not committed via git)
scp <cid>@<laptop>:~/my-hf-bundle/.env .

# Redirect apptainer's build cache to Mimer (big):
export APPTAINER_CACHEDIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/apptainer-cache
mkdir -p $APPTAINER_CACHEDIR

bash scripts/build-model-sif.sh
ls -lh model.sif                      # e.g. 4.2G
```

## 5. Move the SIF to Mimer (if big)

A large SIF (> 2 GiB) shouldn't live on Cephyr permanently:

```bash
# On the login node after building on Alvis:
mkdir -p /mimer/NOBACKUP/groups/<naiss-id>/<cid>/sifs
mv model.sif /mimer/NOBACKUP/groups/<naiss-id>/<cid>/sifs/
```

Or from laptop (if you built there):

```bash
scp ./model.sif <cid>@vera2.c3se.chalmers.se:/mimer/NOBACKUP/groups/<naiss-id>/<cid>/sifs/
```

Symlink or copy into the project folder for sbatch convenience:

```bash
cd /cephyr/users/<cid>/Alvis/my-hf-bundle
ln -sf /mimer/NOBACKUP/groups/<naiss-id>/<cid>/sifs/model.sif model.sif
```

## 6. Laptop smoke test (optional)

**PowerShell / bash / zsh:**

```bash
apptainer run --nv model.sif "Explain gravity in 3 sentences."
```

If you have a GPU on laptop, use `--nv`; otherwise drop it (slow on
CPU but works).

## 7. Cluster smoke test

Fast CPU smoke — just verifies the SIF loads:

```bash
# On Alvis
cd /cephyr/users/<cid>/Alvis/my-hf-bundle
sbatch slurm/cpu-smoke.sbatch
squeue -u $USER                  # wait for R
cat slurm-*-cpu-smoke-*.out
```

Expected: the SIF prints its metadata (from `/opt/model-metadata.txt`)
and the model loads successfully on CPU.

Then GPU smoke:

```bash
sbatch slurm/gpu-t4.sbatch
cat slurm-*-gpu-t4-*.out
```

Expected: `device: cuda`, `gpu: Tesla T4`, short generated completion.

## 8. Run your real prompts

```bash
sbatch --export=ALL,PROMPT="Your question here" slurm/gpu-t4.sbatch
```

For batch inference, write `scripts/infer_batch.py`:

```python
import csv
from hf_sif_bundle import model

with open("/data/prompts.csv") as f:
    for row in csv.DictReader(f):
        r = model.generate(row["prompt"])
        print(row["id"], r["text"])
```

Add a bind mount in your sbatch:

```bash
apptainer run --nv \
    --bind /mimer/NOBACKUP/groups/<naiss-id>/<cid>/prompts:/data \
    --bind $PWD/results:/results \
    model.sif pixi run infer
```

## 9. Retrieve results

**PowerShell:**

```powershell
rsync -avh --progress `
  <cid>@vera2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/my-hf-bundle/results/ `
  .\results\
```

**bash / zsh:**

```bash
rsync -avh --progress \
  <cid>@vera2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/my-hf-bundle/results/ \
  ./results/
```

## 10. Verification checklist

- [ ] `model.sif` exists and `du -h model.sif` matches expectation.
- [ ] `apptainer run model.sif 'ls /opt/model'` lists HF repo files
      (config.json, tokenizer.json, *.safetensors, etc.).
- [ ] Every `slurm/*.sbatch` has your real `--account=<NAISS>`.
- [ ] `cpu-smoke` job completes successfully and logs the baked model name.
- [ ] `gpu-t4` job logs `device: cuda` and a generated completion.
- [ ] `results/responses/*.json` entries have non-empty `text`.

## Troubleshooting

- **Build fails with "429 Too Many Requests"** → HuggingFace rate
  limited you. Wait 5 minutes and retry, or set `HF_TOKEN` to use a
  higher-quota authenticated rate limit.
- **Build fails with "401 Unauthorized"** → gated model; set
  `HF_TOKEN` in `.env`.
- **Build crashes with "no space left on device"** → redirect
  `APPTAINER_CACHEDIR` (step 4B) to Mimer.
- **Runs but `MODEL_DIR not found`** → you're trying to use
  `dev.sif` (which doesn't bake the model) instead of `model.sif`.
  Check your sbatch's `apptainer run` line.
- **Very slow first load per job** → normal; subsequent jobs using
  the same SIF benefit from filesystem caching.
