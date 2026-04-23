# Usage — `03-hf-shared-hub` (step-by-step, zero to results)

A complete walkthrough from an empty folder to your first generated
text, loading a HuggingFace model from C3SE's pre-downloaded hub at
`/mimer/NOBACKUP/Datasets/LLM/huggingface/hub/`.

## 0. What you'll end up with

- An sbatch job on Alvis running your model on a T4 GPU.
- Response text saved to `$RESULTS_DIR/responses/<timestamp>.json`.
- Zero Cephyr quota used by the model weights (mirror is elsewhere).

## 1. Prerequisites

**On laptop** (for dev loop):

- Docker Desktop (Windows / macOS) or Docker Engine (Linux).
- `git` (any recent version).
- Optional: Apptainer on WSL2 / Linux if you want to build SIFs
  locally. On macOS, skip Apptainer locally and build on Alvis.

**On cluster**:

- C3SE account with Alvis allocation (NAISS project ID).
- SSH access to `alvis1.c3se.chalmers.se` / `alvis2.c3se.chalmers.se`.

## 2. Clone the template

Choose a sibling folder for your new project.

**PowerShell (Windows):**

```powershell
Copy-Item . ..\my-hf-inference -Recurse
cd ..\my-hf-inference
```

**bash / zsh (macOS / Linux):**

```bash
cp -r . ../my-hf-inference
cd ../my-hf-inference
```

## 3. Pick a model from C3SE's mirror

SSH to Alvis and list what's available:

```bash
ssh alvis
ls /mimer/NOBACKUP/Datasets/LLM/huggingface/hub/
# → models--google--gemma-2-2b-it, models--meta-llama--Llama-3.1-8B, etc.

# Pick one, then list its snapshots:
ls /mimer/NOBACKUP/Datasets/LLM/huggingface/hub/models--google--gemma-2-2b-it/snapshots/
# → a3f92b... ← one or more commit hashes
```

Pick a snapshot hash. The full snapshot path will be:

```
/mimer/NOBACKUP/Datasets/LLM/huggingface/hub/models--google--gemma-2-2b-it/snapshots/<hash>/
```

## 4. Configure `.env`

On laptop:

**PowerShell:**

```powershell
Copy-Item .env.example .env
```

**bash / zsh:**

```bash
cp .env.example .env
```

Edit `.env` and fill in:

```ini
CEPHYR_USER=<your-cid>
CEPHYR_PROJECT_PATH=/cephyr/users/<your-cid>/Alvis/my-hf-inference
MIMER_GROUP_PATH=/mimer/NOBACKUP/groups/<your-naiss-id>
MIMER_PROJECT_PATH=/mimer/NOBACKUP/groups/<your-naiss-id>/<your-cid>/my-hf-inference
ALVIS_ACCOUNT=<your-naiss-id>

HF_MODEL_SNAPSHOT=/mimer/NOBACKUP/Datasets/LLM/huggingface/hub/models--google--gemma-2-2b-it/snapshots/<hash>/
```

Also fix the Slurm `--account` in every `slurm/*.sbatch`:

```diff
-#SBATCH --account=<PROJECT_ID>
+#SBATCH --account=<your-naiss-id>
```

## 5. Laptop workaround (optional)

`/mimer/...` doesn't exist on your laptop, so local HF dev against
the shared hub path won't work as-is. Two choices:

**Option A — skip laptop HF work, go straight to Alvis.** Valid; the
laptop's role in this example is editing code and git-pushing.

**Option B — use a locally-cached HuggingFace model** to exercise
the same code locally. Download once:

```bash
docker compose up -d dev
docker compose exec dev bash -c "pip install huggingface_hub && \
  huggingface-cli download google/gemma-2-2b-it --local-dir /workspace/.laptop-model"
```

Then temporarily set `HF_MODEL_SNAPSHOT=/workspace/.laptop-model`
while you iterate. Flip it back to the `/mimer/...` path before
pushing.

## 6. Push code to cluster (git-based — recommended)

Create a **public** team remote for this project, then:

```bash
git init -b main
git add .
git commit -m "initial scaffold"
git remote add origin git@github.com:<team>/<project>.git
git push -u origin main
```

On the cluster, clone once:

```bash
ssh alvis
mkdir -p /cephyr/users/<cid>/Alvis
cd /cephyr/users/<cid>/Alvis
git clone git@github.com:<team>/<project>.git my-hf-inference
cd my-hf-inference
# Put your .env here — scp from laptop (not committed):
scp <cid>@<laptop>:~/my-hf-inference/.env .   # or paste via nano
```

> For solo, no-remote runs, use `bash _shared/scripts/sync-to-cephyr.sh`
> from the laptop instead — see
> [`../../docs/cluster-workflow.md`](../../docs/cluster-workflow.md).

## 7. Build the SIF on Alvis

```bash
cd /cephyr/users/<cid>/Alvis/my-hf-inference
export APPTAINER_CACHEDIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/apptainer-cache
mkdir -p $APPTAINER_CACHEDIR
apptainer build dev.sif apptainer/dev.def
```

First build: 2–5 minutes (pulls base layers, installs Pixi + Python).

## 8. Smoke test on the cluster

Start with a fast CPU smoke that just prints environment info:

```bash
sbatch slurm/cpu-smoke.sbatch
squeue -u $USER                           # wait for R state
cat slurm-*-cpu-smoke-*.out               # verify green
```

Expected output: device info, Python version, `transformers` version,
and the resolved `HF_MODEL_SNAPSHOT` path.

Then the T4 GPU smoke that actually loads the model:

```bash
sbatch slurm/gpu-t4.sbatch
```

Expected output: `device: cuda`, `gpu: Tesla T4`, and a short
generated completion from the model.

## 9. Run your real prompts

```bash
# Single prompt
sbatch --export=ALL,PROMPT="Explain gravity in 3 sentences." slurm/gpu-t4.sbatch
```

For batch inference, modify `scripts/infer.py` to iterate a CSV:

```python
import csv
from hf_shared_hub import model

with open("/data/prompts.csv") as f:
    for row in csv.DictReader(f):
        r = model.generate(row["prompt"])
        print(row["id"], r["text"])
```

Bind `/data` in the sbatch:

```bash
#SBATCH ...
apptainer run --nv \
    --bind /mimer/NOBACKUP/groups/<naiss-id>/<cid>/prompts:/data \
    --bind $PWD/results:/results \
    dev.sif pixi run infer
```

## 10. Retrieve results

From laptop:

**PowerShell:**

```powershell
rsync -avh --progress `
  <cid>@vera2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/my-hf-inference/results/ `
  .\results\
```

**bash / zsh:**

```bash
rsync -avh --progress \
  <cid>@vera2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/my-hf-inference/results/ \
  ./results/
```

Open any `results/responses/*.json` to see the generated text.

## 11. Verification checklist

- [ ] `ls /mimer/NOBACKUP/Datasets/LLM/huggingface/hub/` shows your model.
- [ ] `.env` has a snapshot path that exists.
- [ ] Every `slurm/*.sbatch` has your real `--account=<NAISS>`.
- [ ] `cpu-smoke` job shows your resolved snapshot path in the log.
- [ ] `gpu-t4` job shows `device: cuda`, gpu name, and generated text.
- [ ] `results/responses/*.json` has entries with non-empty `text`.

## Troubleshooting pointers

- **"HF_MODEL_SNAPSHOT is not set"** → you didn't propagate `.env` to
  the cluster; `scp` it or set the var in the sbatch.
- **"HF_MODEL_SNAPSHOT=... does not exist"** → the hash changed or
  the model isn't mirrored; re-run the `ls` in step 3.
- **Runs on CPU despite a GPU allocation** → missing `--nv` flag;
  check the sbatch's `apptainer run` line.
- **Cephyr quota warning** → double-check nothing downloaded HF
  weights to your home; the shared-hub flow should touch zero bytes
  of your quota.
