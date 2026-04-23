# Usage — `22-reconstruct-retrain-infer` (step-by-step, zero to a deployable SIF)

A complete walkthrough from an empty folder through the full four-stage
pipeline: architecture **surgery** → **retrain** → **evaluate** →
**bundle** into a deployable SIF. The shipped example swaps an LLM's
classification head with a 6-way head and retrains on the `emotion`
dataset — small enough to run end-to-end on a T4 in about fifteen
minutes.

This is the most complete template in the library. After this one,
you are writing a custom training framework.

## 0. What you'll end up with

Four artifacts, one per stage, all on Mimer:

1. `results/surgeried/<ts>/` — the pretrained backbone with a freshly
   initialized task head (produced by stage 1).
2. `results/checkpoints/<run-id>/` — the fully retrained model plus
   `run_summary.json` (stage 2).
3. `results/eval_report.json` — accuracy, macro-F1, confusion matrix
   on the held-out split (stage 3).
4. `results/bundles/reco-<ts>.sif` — a self-contained Apptainer image
   that ships model + code + env (stage 4).

## 1. Prerequisites

**On laptop** (for dev loop + smoke only):

- Docker Desktop (Windows / macOS) or Docker Engine (Linux).
- `git`.
- The dev-container image pulls Pixi; nothing extra to install on the
  host.

**On cluster**:

- C3SE Alvis account with project ID (NAISS allocation).
- SSH access to `alvis1.c3se.chalmers.se` / `alvis2.c3se.chalmers.se`.
- A Mimer path under `/mimer/NOBACKUP/groups/<naiss-id>/`. Training
  checkpoints of even a small model (distilbert at 260 MB) produce
  ~500 MB per `save_total_limit=2` retained epoch; any realistic
  surgery target (7B+) will not fit in Cephyr's 30 GiB quota.
- A HuggingFace token for gated bases (`HF_TOKEN` in `.env`).

## 2. Clone the template

**PowerShell (Windows):**

```powershell
Copy-Item . ..\my-reco -Recurse
cd ..\my-reco
```

**bash / zsh (macOS / Linux):**

```bash
cp -r . ../my-reco
cd ../my-reco
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

Open `.env` and set at least:

```ini
CEPHYR_USER=<cid>
CEPHYR_PROJECT_PATH=/cephyr/users/<cid>/Alvis/my-reco

# Mimer, always — not Cephyr
RESULTS_HOST=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-reco/results
MODELS_HOST=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-reco/models
DATA_HOST=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-reco/data

HF_HOME=/workspace/.hf-cache
TRANSFORMERS_CACHE=/workspace/.hf-cache

# Base model + target task
HF_MODEL=distilbert-base-uncased
HF_MODEL_SNAPSHOT=
HF_TOKEN=<hf_token_if_gated>
HF_DATASET=emotion
NUM_LABELS=6

# Training knobs (defaults are tuned for the shipped distilbert example)
NUM_EPOCHS=3
PER_DEVICE_BATCH=16
GRAD_ACCUM=1
LEARNING_RATE=2e-5
MAX_SEQ_LEN=128

# Declarative surgery spec
SURGERY_CONFIG=configs/surgery.yaml
```

Edit `configs/surgery.yaml` if you want something other than the
shipped `replace_classification_head` operation (see §9).

Fix the Slurm `--account` placeholder in every sbatch:

```diff
-#SBATCH --account=<PROJECT_ID>
+#SBATCH --account=<naiss-id>
```

## 4. Laptop smoke test (imports + surgery + quick retrain)

The shipped example is small enough that laptop-end-to-end is
feasible for a sanity check (CPU is slow but tolerable at 3 epochs ×
distilbert):

**PowerShell:**

```powershell
docker compose up -d dev
docker compose exec dev pixi install
docker compose exec dev pixi run smoke
docker compose exec dev pixi run surgery
# The surgery command prints results/surgeried/<ts>/ — copy it:
docker compose exec dev pixi run train --model /results/surgeried/<ts>
docker compose exec dev pixi run eval --ckpt /results/checkpoints/<run-id>
```

**bash / zsh:**

```bash
docker compose up -d dev
docker compose exec dev pixi install
docker compose exec dev pixi run smoke
docker compose exec dev pixi run surgery
docker compose exec dev pixi run train --model /results/surgeried/<ts>
docker compose exec dev pixi run eval --ckpt /results/checkpoints/<run-id>
```

Expected:

- `smoke` prints library versions and `cuda_available`
  (typically `false` on a laptop).
- `surgery` prints a JSON with `trainable_params`, `total_params`,
  `out_dir`.
- `train` finishes in ~10–20 minutes on a laptop CPU; creates
  `results/checkpoints/<run-id>/` with `run_summary.json`.
- `eval` prints test accuracy ~0.92 and F1-macro near 0.9.

For any real surgery target (7B+ LLMs), skip laptop retrain — go
straight to Alvis.

## 5. Pick / customize the surgery

The four-stage pipeline is:

```
  surgery        retrain             evaluate        bundle
  (surgery.py)   (accelerate+train)  (evaluate.py)   (apptainer build)
```

Stage 1 is where the architecture change happens. The shipped code
implements a single operation in `src/reco/surgery.py`:

- `replace_classification_head` — load a backbone with
  `AutoModelForSequenceClassification`, let HF attach a fresh
  `(hidden_size, num_labels)` head, optionally freeze the backbone.

To substitute your own surgery:

1. Add a new function in `src/reco/surgery.py`, e.g. a regression
   head, an adapter insertion, an attention swap.
2. Extend the dispatch in `run()` so that a new `operation:` value in
   `configs/surgery.yaml` hits your function.
3. If the training loss / collator needs to change (e.g., MSE for
   regression), edit `src/reco/train.py` accordingly.

Typical extension points called out in `surgery.py`'s docstring:
regression heads, freeze/unfreeze by layer index, adapter injection,
attention-implementation swap.

## 6. Build the SIF on Alvis

Push code (git, recommended):

```bash
git init -b main
git add .
git commit -m "initial reco scaffold"
git remote add origin git@github.com:<team>/<project>.git
git push -u origin main

ssh alvis
mkdir -p /cephyr/users/<cid>/Alvis
cd /cephyr/users/<cid>/Alvis
git clone git@github.com:<team>/<project>.git my-reco
cd my-reco
scp <cid>@<laptop>:~/my-reco/.env .        # never committed
```

Build the dev image (once per env change):

```bash
export APPTAINER_CACHEDIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/apptainer-cache
mkdir -p "$APPTAINER_CACHEDIR"
apptainer build dev.sif apptainer/dev.def
```

3–6 minutes first time.

> **Cephyr discipline.** Only code and `dev.sif` live on Cephyr.
> Surgeried models, checkpoints, wandb runs, eval dumps, bundled SIFs
> — all on Mimer.

## 7. Cluster setup (one-time)

Create the Mimer layout and wire the HF cache:

```bash
MIMER=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-reco
mkdir -p $MIMER/{data,results,models,hf-cache,wandb,apptainer-cache}
mkdir -p $MIMER/results/{surgeried,checkpoints,bundles}

echo "HF_HOME=$MIMER/hf-cache" >> .env
echo "TRANSFORMERS_CACHE=$MIMER/hf-cache" >> .env
echo "WANDB_DIR=$MIMER/wandb" >> .env
```

Fix the `--account` placeholder in all four sbatch files:

```bash
sed -i 's/<PROJECT_ID>/<naiss-id>/' slurm/surgery.sbatch slurm/train.sbatch slurm/eval.sbatch slurm/bundle.sbatch
```

## 8. Cluster smoke test

Grab an interactive T4 for twenty minutes and check the container:

```bash
srun --account=<naiss-id> --partition=alvis --time=00:20:00 \
     --gpus-per-node=T4:1 --cpus-per-task=4 --mem=16G --pty bash

apptainer exec --nv --bind .:/workspace ./dev.sif pixi run smoke
apptainer exec --nv --bind .:/workspace ./dev.sif pixi run info
exit
```

Expected: versions printed, `cuda_available: true`, one GPU visible.

## 9. Run the real workload — four-stage pipeline

Each stage is a separate sbatch with its own resource profile and its
own output path. Submit them sequentially; later stages depend on the
artifact path from the previous one.

### Stage 1 — surgery (CPU only, ~20 min)

`slurm/surgery.sbatch`:

```
#SBATCH --time=0-00:20:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
# no GPU — surgery is CPU work
```

Run:

```bash
sbatch slurm/surgery.sbatch
tail -f slurm-reco-surgery-*.out
```

The script writes `$RESULTS_DIR/surgeried/<ts>/` and prints the path
on its last line. Capture it:

```bash
SURGERIED=$(ls -td $MIMER/results/surgeried/*/ | head -1)
echo $SURGERIED
```

### Stage 2 — retrain (T4, ~4h wall)

`slurm/train.sbatch`:

```
#SBATCH --time=0-04:00:00
#SBATCH --gpus-per-node=T4:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
```

For bigger surgery targets (7B+), promote to A100 × 4 by copying the
knobs from `21-distributed-finetune/slurm/train-a100x4.sbatch`
(`--gpus-per-node=A100:4`, `--ntasks-per-node=4`, `--cpus-per-task=8`,
`--mem=256G`, `--time=0-24:00:00`) and swap `configs/accelerate/single.yaml` (via `ACCELERATE_CONFIG` env var)
for one of the multi-GPU configs in `21-distributed-finetune/configs/accelerate/`.

Run:

```bash
sbatch --export=ALL,MODEL=$SURGERIED slurm/train.sbatch
tail -f slurm-reco-train-*.out
```

Captures checkpoint path:

```bash
CKPT=$(ls -td $MIMER/results/checkpoints/*/ | head -1)
echo $CKPT
```

### Stage 3 — evaluate (T4, ~30 min)

`slurm/eval.sbatch`:

```
#SBATCH --time=0-00:30:00
#SBATCH --gpus-per-node=T4:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
```

Run:

```bash
sbatch --export=ALL,CKPT=$CKPT slurm/eval.sbatch
tail -f slurm-reco-eval-*.out
```

Output: `$RESULTS_DIR/eval_report.json` with `accuracy`, `f1_macro`,
confusion matrix. On the shipped distilbert+emotion example, expect
accuracy ≈ 0.92.

### Stage 4 — bundle into a deployable SIF (CPU, ~30 min)

`slurm/bundle.sbatch` generates an Apptainer definition on the fly
that copies `pixi.toml`, source, configs and the trained checkpoint
into `/opt/model` inside a fresh SIF, and builds it:

```
#SBATCH --time=0-00:30:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
```

Run:

```bash
sbatch --export=ALL,CKPT=$CKPT slurm/bundle.sbatch
```

Output: `$PWD/results/bundles/reco-<ts>.sif`. The SIF's `%runscript`
invokes `pixi run eval --ckpt /opt/model "$@"`, so any downstream user
can:

```bash
apptainer run --nv reco-<ts>.sif --split test
```

without needing the source tree.

## 10. Retrieve results

Pull reports and the deployable SIF to the laptop. Leave the
surgeried weights and raw checkpoint shards on Mimer.

**PowerShell:**

```powershell
rsync -avh --progress `
  "<cid>@vera2.c3se.chalmers.se:/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-reco/results/eval_report.json" `
  .\results\

rsync -avh --progress `
  "<cid>@vera2.c3se.chalmers.se:/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-reco/results/bundles/" `
  .\results\bundles\
```

**bash / zsh:**

```bash
rsync -avh --progress \
  "<cid>@vera2.c3se.chalmers.se:/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-reco/results/eval_report.json" \
  ./results/

rsync -avh --progress \
  "<cid>@vera2.c3se.chalmers.se:/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-reco/results/bundles/" \
  ./results/bundles/
```

Share the SIF with collaborators:

```bash
scp results/bundles/reco-<ts>.sif <peer>@<their-host>:/some/path/
```

They run it without needing the source tree:

```bash
apptainer run --nv reco-<ts>.sif --split test
```

## 11. Verification checklist

- [ ] Every `slurm/*.sbatch` has your real `--account=<naiss-id>`.
- [ ] `RESULTS_HOST`, `MODELS_HOST`, `HF_HOME`, `WANDB_DIR` all point
      at Mimer, never `$HOME`, never Cephyr.
- [ ] `configs/surgery.yaml` matches your intent
      (`operation`, `num_labels`, `freeze_base`).
- [ ] Stage 1 wrote `results/surgeried/<ts>/surgery_summary.json`
      with the expected `trainable_params` count.
- [ ] Stage 2 wrote `results/checkpoints/<run-id>/run_summary.json`
      with non-empty `ckpt_dir`.
- [ ] Stage 3 wrote `results/eval_report.json` and metrics look sane
      (≈0.92 accuracy on the shipped example).
- [ ] Stage 4 produced `results/bundles/reco-<ts>.sif`, and
      `apptainer run reco-<ts>.sif --help` works.
- [ ] `du -sh $MIMER/results/checkpoints` is bounded by
      `save_total_limit` × per-checkpoint size.
- [ ] No HF downloads landed in `$HOME/.cache/huggingface`.

## 12. Troubleshooting

- **`Surgery operation '<x>' not implemented`** — you set an
  `operation:` in `configs/surgery.yaml` that has no handler in
  `src/reco/surgery.py`. Add a function and hook it up in `run()`.
- **`num_labels` mismatch** — `NUM_LABELS` in `.env`,
  `configs/surgery.yaml`, and the dataset's label count must all
  agree. Error looks like `ignore_mismatched_sizes` warnings plus
  garbage accuracy.
- **Stage 2 loads the wrong model** — you passed the raw `HF_MODEL`
  path instead of the surgeried directory. Always use
  `--export=ALL,MODEL=$SURGERIED` where `$SURGERIED` is the stage-1
  output path.
- **Stage 3's `_label_to_int` returns -1** — HF pipeline returned
  `LABEL_N`-style strings because `id2label` wasn't carried through.
  Ensure the dataset's features include a `ClassLabel` or populate
  `id2label` explicitly at surgery time.
- **Stage 4 SIF build OOM / slow** — bundling copies the full
  checkpoint tree. Make sure `$CKPT` points at the final consolidated
  checkpoint, not the full `checkpoints/<run-id>/` dir with all
  intermediate epochs.
- **`HF_HOME` silently pointed to `$HOME`** — on Alvis the default
  is `~/.cache/huggingface`, which lives on the 30 GiB Cephyr user
  quota. Always export `HF_HOME` (and `TRANSFORMERS_CACHE`) to a
  Mimer path before any `from_pretrained` call. Set it in `.env` and
  verify it survives the sbatch env propagation.
- **Cephyr quota warnings mid-run** — a stage wrote to Cephyr.
  Typical causes: `RESULTS_DIR` not overridden, `$TMPDIR` fell back
  to `/cephyr`, a DataLoader worker used a local path. Check
  `lfs quota -u $USER /cephyr`, redirect offenders to Mimer, restart.
- **`scp` of the SIF fails with "No space left"** — the Cephyr disk
  filled because the bundle landed there instead of Mimer. Point
  `RESULTS_DIR` at Mimer and rebuild.
- **Downstream `apptainer run reco-<ts>.sif` crashes on missing
  `HF_HOME`** — the bundle's `%environment` sets `HF_MODEL_SNAPSHOT`
  but not `HF_HOME`. Either bind a Mimer path at runtime
  (`--bind /mimer/...:/cache -e HF_HOME=/cache`) or bake a default
  into the bundle def file before building.
