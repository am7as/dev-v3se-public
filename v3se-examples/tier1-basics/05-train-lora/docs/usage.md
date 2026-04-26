# Usage — `05-train-lora` (step-by-step, zero to results)

A complete walkthrough from an empty folder to a trained LoRA adapter
and a generation from that adapter. The default model is tiny
(`sshleifer/tiny-gpt2`, 8 MB) so the full loop runs on CPU in seconds
for the laptop smoke, and on a T4 in under a minute on Alvis. Everything
uses HuggingFace `transformers` + `peft` + `trl`.

## 1. What you'll end up with

- A LoRA adapter at
  `$MIMER_PROJECT_PATH/adapters/<timestamp>/` (cluster) or
  `$RESULTS_DIR/adapters/<timestamp>/` (laptop): adapter weights +
  tokenizer + `run_summary.json`.
- A generation from the base model + adapter via
  `pixi run infer --adapter-dir ... --prompt "..."`.
- A reproducible recipe in `.env` (model, dataset, LoRA hyperparams)
  so you can swap in a real base and dataset without touching code.

## 2. Prerequisites

**On laptop** (dev loop):

- Docker Desktop (Windows / macOS) or Docker Engine (Linux).
- `git`. A few GB of free RAM for the tiny-model CPU run.
- Optional: `HF_TOKEN` if you plan to swap to a gated model (Llama,
  Gemma) later.

**On cluster**:

- C3SE account with Alvis allocation (`<PROJECT_ID>` = NAISS ID).
- Cephyr home `/cephyr/users/<cid>/Alvis/` (code + SIF).
- Mimer project space `/mimer/NOBACKUP/groups/<naiss-id>/<cid>/...`
  (HF cache, adapters, results — NEVER `$HOME`).
- SSH to `alvis2.c3se.chalmers.se`.

## 3. Clone the template

**PowerShell (Windows):**

```powershell
Copy-Item . ..\my-lora-finetune -Recurse
cd ..\my-lora-finetune
```

**bash / zsh (macOS / Linux):**

```bash
cp -r . ../my-lora-finetune
cd ../my-lora-finetune
```

## 4. Configure `.env`

**PowerShell:**

```powershell
Copy-Item .env.example .env
```

**bash / zsh:**

```bash
cp .env.example .env
```

Edit `.env`. Keep `HF_MODEL=sshleifer/tiny-gpt2` for the first pass;
swap to something real (Gemma, Mistral, Qwen) once the loop is green.

```ini
# Container paths — don't change.
DATA_DIR=/data
RESULTS_DIR=/results
MODELS_DIR=/models
WORKSPACE_DIR=/workspace
LOG_LEVEL=INFO

# Host bind mounts — blank for sibling defaults (laptop only).
DATA_HOST=
RESULTS_HOST=
MODELS_HOST=

# Cephyr (code) + Alvis login.
CEPHYR_USER=<cid>
CEPHYR_PROJECT_PATH=/cephyr/users/<cid>/Alvis/my-lora-finetune
CEPHYR_TRANSFER_HOST=alvis2.c3se.chalmers.se
ALVIS_LOGIN_HOST=alvis2.c3se.chalmers.se
ALVIS_ACCOUNT=<naiss-id>
MIMER_GROUP_PATH=/mimer/NOBACKUP/groups/<naiss-id>
MIMER_PROJECT_PATH=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-lora-finetune

# Base model. Tiny for first runs.
HF_MODEL=sshleifer/tiny-gpt2
HF_MODEL_SNAPSHOT=
HF_TOKEN=

# HF_HOME MUST point inside the workspace (laptop) or Mimer (cluster).
# NEVER leave this pointing at $HOME — $HOME on Alvis compute nodes is
# tiny and will fill in minutes.
HF_HOME=/workspace/.hf-cache
TRANSFORMERS_CACHE=/workspace/.hf-cache

# Dataset: empty = the in-memory 5-row sample.
HF_DATASET=

# LoRA hyperparameters (defaults are small on purpose).
LORA_R=8
LORA_ALPHA=16
LORA_DROPOUT=0.05
NUM_EPOCHS=1
BATCH_SIZE=4
LEARNING_RATE=1e-4

# Weights & Biases (optional).
WANDB_API_KEY=
WANDB_PROJECT=v3se-lora
WANDB_MODE=offline

JUPYTER_PORT=7888
```

Fix the Slurm `--account` in `slurm/train-t4.sbatch`:

```diff
-#SBATCH --account=<PROJECT_ID>
+#SBATCH --account=<naiss-id>
```

## 5. Laptop smoke test

Bring up dev, install Pixi env (downloads torch + transformers + peft
+ trl — takes 3-5 min first time), then train + generate.

**PowerShell:**

```powershell
docker compose up -d dev
docker compose exec dev pixi install
docker compose exec dev pixi run smoke
docker compose exec dev pixi run train
# Train prints the adapter path on the last line.
# Plug that path into infer:
docker compose exec dev pixi run infer `
  --adapter-dir /results/adapters/<ts>/ `
  --prompt "Once upon a time"
```

**bash / zsh:**

```bash
docker compose up -d dev
docker compose exec dev pixi install
docker compose exec dev pixi run smoke
docker compose exec dev pixi run train
docker compose exec dev pixi run infer \
  --adapter-dir /results/adapters/<ts>/ \
  --prompt "Once upon a time"
```

Expected: tiny-gpt2 trains for 1 epoch in under a minute. The
adapter dir contains `adapter_config.json`,
`adapter_model.safetensors`, tokenizer files, and
`run_summary.json`.  `pixi run infer` loads the base, attaches the
adapter, and completes the prompt.

## 6. Build step (not applicable)

No image bake — dev-mode SIF is bind-mounted. Skip to section 8.

> **Note.** Once the loop works and you've chosen a real base model,
> you can bake an app-mode SIF that bundles the adapter for shipping;
> that flow lives in `13-train-infer-pipeline`.

## 7. Push to cluster

### Git (preferred)

Never commit `HF_TOKEN`, `WANDB_API_KEY`, or a trained adapter.
`.gitignore` already excludes `results/` and `.hf-cache/`.

```bash
git init -b main
git add .env.example .gitignore pixi.toml pyproject.toml README.md \
        apptainer/ configs/ docker-compose.yml docs/ scripts/ slurm/ \
        src/ tests/
git commit -m "initial train-lora scaffold"
git remote add origin git@github.com:<team>/my-lora-finetune.git
git push -u origin main
```

On cluster:

```bash
ssh <cid>@alvis2.c3se.chalmers.se
mkdir -p /cephyr/users/<cid>/Alvis
cd /cephyr/users/<cid>/Alvis
git clone git@github.com:<team>/my-lora-finetune.git
cd my-lora-finetune
scp <cid>@<laptop-hostname>:.env .      # or scp .env from laptop
```

### rsync (fallback — solo workflow)

```bash
bash ../../_shared/scripts/sync-to-cephyr.sh
```

## 8. Cluster setup

SSH in, set `APPTAINER_CACHEDIR` to Mimer (else your first `pixi
install` + `torch` wheel will obliterate your Cephyr quota), build
the dev SIF, create the Mimer project tree for caches and adapters.

```bash
ssh <cid>@alvis2.c3se.chalmers.se
cd /cephyr/users/<cid>/Alvis/my-lora-finetune

export APPTAINER_CACHEDIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/apptainer-cache
mkdir -p "$APPTAINER_CACHEDIR"

apptainer build dev.sif apptainer/dev.def

mkdir -p /mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-lora-finetune/{hf-cache,adapters,results}
```

First build: 2-5 min. `dev.sif` is ~700 MB.

Override the `HF_HOME` and `RESULTS_DIR` in `.env` **for the cluster**
so caches + adapters land on Mimer, not Cephyr. Either edit `.env` on
Cephyr or add the exports to the sbatch:

```bash
# at the top of slurm/train-t4.sbatch, before `apptainer run`:
export HF_HOME=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-lora-finetune/hf-cache
export TRANSFORMERS_CACHE="$HF_HOME"
export RESULTS_DIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-lora-finetune/results
# then:
apptainer run --nv \
    --bind .:/workspace \
    --bind "$HF_HOME":"$HF_HOME" \
    --bind "$RESULTS_DIR":/results \
    "$SIF" pixi run train
```

(The template's default sbatch just uses `$PWD/.hf-cache` and
`$PWD/results`, which works but lands in Cephyr. Override as above for
anything non-trivial.)

## 9. Cluster smoke

Run the training job on 1x T4 first:

```bash
sbatch slurm/train-t4.sbatch
squeue -u $USER
cat slurm-train-lora-*.out
```

Expected output: HF `Trainer` logs 1 epoch, a final "Adapter saved
to: /results/adapters/<ts>/" line, and a JSON blob with the run
summary.

Sanity-check the adapter size — LoRA weights are tiny:

```bash
ls -lh /mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-lora-finetune/adapters/<ts>/
# adapter_model.safetensors: ~200 KB for tiny-gpt2 at r=8
# Base model weights are NOT copied — that's the whole point.
```

## 10. Run the real workload

Swap tiny model + in-memory data for something real.

Edit `.env` (or override in the sbatch with `--export=ALL,HF_MODEL=...`):

```ini
HF_MODEL=google/gemma-2-2b-it      # or mistralai/Mistral-7B-Instruct-v0.3
HF_TOKEN=hf_...                    # required for gated models
HF_DATASET=tatsu-lab/alpaca        # or a path to a JSONL under /data
NUM_EPOCHS=3
BATCH_SIZE=8
LEARNING_RATE=2e-4
```

For larger bases, move to A40 / A100 — edit `slurm/train-t4.sbatch`:

```diff
-#SBATCH --gpus-per-node=T4:1
-#SBATCH --mem=32G
-#SBATCH --time=0-01:00:00
+#SBATCH --gpus-per-node=A40:1
+#SBATCH --mem=64G
+#SBATCH --time=0-06:00:00
```

Submit:

```bash
sbatch slurm/train-t4.sbatch     # filename still fine — rename if you want
```

When the job finishes, generate from the trained adapter:

```bash
ADAPTER=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-lora-finetune/adapters/<ts>

apptainer run --nv \
    --bind .:/workspace \
    --bind /mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-lora-finetune:/mimer-project \
    dev.sif pixi run infer \
        --adapter-dir "/mimer-project/adapters/<ts>" \
        --prompt "Instruction: Write a haiku about Alvis.\nResponse:"
```

(Run interactively from a login node for a one-shot check, or wrap in
an sbatch for batch generation.)

## 11. Retrieve results

Adapters are small (MB-scale). Pull the `adapters/` directory back to
the laptop.

**PowerShell:**

```powershell
rsync -avh --progress `
  <cid>@alvis2.c3se.chalmers.se:/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-lora-finetune/adapters/ `
  .\results\adapters\
```

**bash / zsh:**

```bash
rsync -avh --progress \
  <cid>@alvis2.c3se.chalmers.se:/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-lora-finetune/adapters/ \
  ./results/adapters/
```

Or:

```bash
bash ../../_shared/scripts/sync-from-cephyr.sh
```

Inspect the run summary:

**PowerShell:**

```powershell
Get-Content .\results\adapters\<ts>\run_summary.json
```

**bash / zsh:**

```bash
jq . results/adapters/<ts>/run_summary.json
```

## 12. Verification checklist

- [ ] `.env` filled in: `HF_MODEL`, `HF_HOME` (NOT `$HOME`), and if
      swapping to a gated model, `HF_TOKEN`.
- [ ] `slurm/train-t4.sbatch` has real `--account=<naiss-id>`.
- [ ] Laptop `pixi run train` completed and wrote
      `../results/adapters/<ts>/adapter_model.safetensors`.
- [ ] `pixi run infer --adapter-dir ...` produced a completion on
      laptop.
- [ ] On cluster, `APPTAINER_CACHEDIR` and `HF_HOME` both point at
      Mimer — verify with `echo $APPTAINER_CACHEDIR $HF_HOME`.
- [ ] `sbatch slurm/train-t4.sbatch` completed; `.out` shows 1 epoch
      of training + adapter path.
- [ ] Mimer project tree has
      `adapters/<ts>/adapter_model.safetensors` and
      `run_summary.json`.
- [ ] Cephyr quota unchanged by HF model weights (they're in Mimer's
      `hf-cache`).
- [ ] Adapter directory rsynced back to laptop.

## 13. Troubleshooting

- **`OSError: [Errno 28] No space left on device` during
  `pixi install` or HF download** → `HF_HOME` or pip cache is
  pointing at `$HOME`. On Alvis, `$HOME` is ~20 GB. Explicitly
  `export HF_HOME=/mimer/...` and `export PIP_CACHE_DIR=/mimer/...`
  before installing.
- **`OutOfMemoryError: CUDA out of memory` on T4** → base model too
  big. Drop batch size (`BATCH_SIZE=2`), shorten sequences, or
  upgrade to A40 (48 GB) / A100. 7B+ models need A40 or bigger even
  for LoRA.
- **`ValueError: Your setup doesn't support bf16` on T4** → T4 is
  fp16/fp32 only (no bf16). Default training_args in this template
  auto-pick fp16 on CUDA. If you forced `bf16=True`, undo it for T4.
- **HF gated-model 401 error** → `HF_TOKEN` not set, or you didn't
  accept the model's license on huggingface.co. Click through the
  license first, then `huggingface-cli login` once inside the
  container to verify.
- **`peft.errors.TargetModulesNotFound`** → the default LoRA target
  modules don't match this architecture. Pass
  `--target-modules q_proj,v_proj` (Llama-family) or check the
  model card for attention layer names.
- **Training "finished" in 0 seconds** → dataset was empty. Confirm
  `HF_DATASET` loads: `python -c "from datasets import load_dataset; print(load_dataset('tatsu-lab/alpaca', split='train[:5]'))"`.
- **Adapter loads on base model but outputs gibberish** → chat
  template mismatch. The base model expects a specific format (e.g.
  Gemma uses `<start_of_turn>user ...`). Update your training data to
  that format, retrain.
