# Usage — `21-distributed-finetune` (step-by-step, zero to a 4× A100 run)

A complete walkthrough from an empty folder to a full-parameter,
multi-GPU finetune on 4× A100 using `accelerate` with DeepSpeed
(ZeRO-2 / ZeRO-3) or FSDP. The tier3 examples assume you have already
walked through tier1 and tier2 at least once — this doc focuses on the
distributed-training parts that are new here.

## 0. What you'll end up with

- An sbatch job on Alvis running a 7B–13B full-parameter finetune on
  4× A100.
- Sharded checkpoints saved to `$RESULTS_DIR/checkpoints/<run-id>/`,
  backed by Mimer (not Cephyr — see step 4).
- A `run_summary.json` per run and a held-out eval report.
- Optional wandb / mlflow tracking, also written to Mimer.

## 1. Prerequisites

**On laptop** (for dev loop + smoke only — never the real train):

- Docker Desktop (Windows / macOS) or Docker Engine (Linux).
- `git` (any recent version).
- Pixi is baked into the container image; no host install needed.
- Apptainer is optional on the laptop; the SIF gets built on Alvis.

**On cluster**:

- C3SE Alvis account with A100 allocation.
- SSH access to `alvis1.c3se.chalmers.se` / `alvis2.c3se.chalmers.se`.
- A Mimer path under `/mimer/NOBACKUP/groups/<naiss-id>/` — the 30 GiB
  / 60k-file Cephyr quota cannot hold a real distributed checkpoint.
  One `save_steps=500` dump of a 7B sharded checkpoint is roughly
  30–60 GB, and `save_total_limit=3` means three are kept at a time.
- A HuggingFace token if your base model is gated
  (`HF_TOKEN` in `.env`).

## 2. Clone the template

Pick a sibling folder for your new project.

**PowerShell (Windows):**

```powershell
Copy-Item . ..\my-dist-ft -Recurse
cd ..\my-dist-ft
```

**bash / zsh (macOS / Linux):**

```bash
cp -r . ../my-dist-ft
cd ../my-dist-ft
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

Open `.env` and fill in at least:

```ini
CEPHYR_USER=<cid>
CEPHYR_PROJECT_PATH=/cephyr/users/<cid>/Alvis/my-dist-ft

# Weights, checkpoints, wandb — all live on Mimer, NOT Cephyr.
RESULTS_HOST=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-dist-ft/results
MODELS_HOST=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-dist-ft/models
DATA_HOST=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-dist-ft/data

# HF cache MUST NOT land in $HOME (Cephyr user quota).
HF_HOME=/workspace/.hf-cache

# Base model + target dataset
HF_MODEL=meta-llama/Llama-3.1-8B-Instruct
HF_MODEL_SNAPSHOT=
HF_TOKEN=<hf_token_if_gated>

HF_DATASET=tatsu-lab/alpaca
HF_DATASET_SPLIT=train

# Distributed strategy: ds_zero2 | ds_zero3 | fsdp
ACCELERATE_CONFIG=ds_zero2

# Per-GPU batch x grad-accum x world-size = effective batch.
# 4 x 8 x 4 = 128 on 4× A100. Shrink if OOM.
PER_DEVICE_BATCH=4
GRAD_ACCUM=8
LEARNING_RATE=2e-5
MAX_SEQ_LEN=2048

WANDB_API_KEY=<optional>
WANDB_PROJECT=v3se-dist-ft
WANDB_MODE=offline
```

Then fix the Slurm `--account` in every `slurm/*.sbatch`:

```diff
-#SBATCH --account=<PROJECT_ID>
+#SBATCH --account=<naiss-id>
```

## 4. Laptop smoke test (imports + env + GPU count)

Start the dev container, install the Pixi env, run the smoke script:

**PowerShell:**

```powershell
docker compose up -d dev
docker compose exec dev pixi install
docker compose exec dev pixi run smoke
```

**bash / zsh:**

```bash
docker compose up -d dev
docker compose exec dev pixi install
docker compose exec dev pixi run smoke
```

Expected: JSON printed with `torch`, `transformers`, `accelerate`,
`deepspeed`, `trl`, `datasets` versions and `cuda_available`
(typically `false` on a laptop — that's fine). **Do not attempt a
real training run on the laptop.** A 7B bf16 model alone is ~14 GB of
weights; add optimizer state and activations and you are well past any
laptop.

## 5. Pick the `accelerate` strategy

Three hand-tuned configs ship under `configs/accelerate/`. Pick one and
set `ACCELERATE_CONFIG=<name>` in `.env`:

| File            | Strategy           | Pick this when                                                        |
|-----------------|--------------------|-----------------------------------------------------------------------|
| `ds_zero2.yaml` | DeepSpeed ZeRO-2   | The model (in bf16) fits on **one** A100. Fastest option.             |
| `ds_zero3.yaml` | DeepSpeed ZeRO-3   | The model does **not** fit on one GPU. Partitions params too.         |
| `fsdp.yaml`     | PyTorch FSDP       | You prefer pure-PyTorch sharding (no DeepSpeed dependency).           |

Rule of thumb on 4× A100 40 GB: ≤7B → `ds_zero2`; 13B → `ds_zero3`;
70B+ → `fsdp` with `fsdp_offload_params: true` and far more GPUs.

All three configs have `num_processes: 4` to match
`--gpus-per-node=A100:4`. If you change GPU count, edit that field too.

Inside the sbatch the strategy lookup is:

```
accelerate launch --config_file configs/accelerate/${ACCELERATE_CONFIG}.yaml scripts/train.py
```

The `pixi run train` task hardcodes `ds_zero2` for quick local use; the
sbatch is what you should change for production.

## 6. Build the SIF on Alvis

Push the code to the cluster (git — recommended):

```bash
git init -b main
git add .
git commit -m "initial dist-ft scaffold"
git remote add origin git@github.com:<team>/<project>.git
git push -u origin main

ssh alvis
mkdir -p /cephyr/users/<cid>/Alvis
cd /cephyr/users/<cid>/Alvis
git clone git@github.com:<team>/<project>.git my-dist-ft
cd my-dist-ft
scp <cid>@<laptop>:~/my-dist-ft/.env .    # never committed
```

Build the dev image (run once per env change):

```bash
export APPTAINER_CACHEDIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/apptainer-cache
mkdir -p "$APPTAINER_CACHEDIR"
apptainer build dev.sif apptainer/dev.def
```

First build is 3–6 minutes; subsequent rebuilds are cached.

> **Cephyr discipline.** `dev.sif` itself is OK on Cephyr (~2–4 GB).
> `HF_HOME`, checkpoints, wandb runs, eval dumps — **never** Cephyr.
> Ensure `RESULTS_HOST`, `MODELS_HOST`, `DATA_HOST` all point under
> `/mimer/NOBACKUP/groups/<naiss-id>/...`.

## 7. Cluster setup (one-time)

Create the Mimer layout referenced by `.env` and wire `HF_HOME` into a
fresh Mimer directory:

```bash
MIMER=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-dist-ft
mkdir -p $MIMER/{data,results,models,hf-cache,wandb,apptainer-cache}

# Force HF to cache on Mimer, never $HOME
echo "HF_HOME=$MIMER/hf-cache" >> .env
echo "TRANSFORMERS_CACHE=$MIMER/hf-cache" >> .env
echo "WANDB_DIR=$MIMER/wandb" >> .env
```

Fix the `--account` placeholder in both sbatch files:

```bash
sed -i 's/<PROJECT_ID>/<naiss-id>/' slurm/train-a100x4.sbatch slurm/eval-a100.sbatch
```

## 8. Cluster smoke test (small, cheap, fast)

Before burning 24 hours on 4× A100, confirm the container is healthy.
An interactive one-GPU session is enough for a smoke:

```bash
srun --account=<naiss-id> --partition=alvis --time=00:20:00 \
     --gpus-per-node=T4:1 --cpus-per-task=4 --mem=16G --pty bash

apptainer exec --nv --bind .:/workspace ./dev.sif pixi run smoke
apptainer exec --nv --bind .:/workspace ./dev.sif pixi run info
exit
```

Expected: `cuda_available: true`, `gpu_count: 1`, package versions
sane. If `pixi install` has not run inside the container, the first
call will do it — a few minutes the first time.

## 9. Run the real 4× A100 workload

`slurm/train-a100x4.sbatch` is the production job. Its header:

```bash
#SBATCH --account=<naiss-id>
#SBATCH --partition=alvis
#SBATCH --time=1-00:00:00           # 24h — raise for larger datasets
#SBATCH --gpus-per-node=A100:4
#SBATCH --cpus-per-task=16
#SBATCH --mem=256G
```

Notes:

- `--gpus-per-node=A100:4` — four A100s on one node; `num_processes`
  in the chosen `accelerate` config must equal 4.
- `--cpus-per-task=16` — 4 CPUs per GPU is a good default for the
  DataLoader workers TRL spawns.
- `--mem=256G` — a 7B full-param run plus optimizer + activations +
  DataLoader buffers is routinely in the 150–200 GB host-RAM range.
- `--time=1-00:00:00` — bump to `0-24:00:00` or longer for bigger
  data. If you pass the wall, see §12.

Submit and watch:

```bash
sbatch slurm/train-a100x4.sbatch
squeue -u $USER                                       # wait for R
tail -f slurm-dist-ft-a100x4-*.out
# wandb (if enabled): https://wandb.ai/<user>/v3se-dist-ft
```

For a held-out eval of any intermediate checkpoint:

```bash
CKPT=$MIMER/results/checkpoints/<run-id>/checkpoint-500
sbatch --export=ALL,CKPT=$CKPT slurm/eval-a100.sbatch
```

`eval-a100.sbatch` asks for a single A100 for an hour — tiny compared
to the training job.

## 10. Retrieve results

Pull the evaluation and run-summary JSONs back to your laptop. Large
checkpoint shards should stay on Mimer until you bundle them for
deployment.

**PowerShell:**

```powershell
rsync -avh --progress `
  "<cid>@vera2.c3se.chalmers.se:/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-dist-ft/results/" `
  .\results\
```

**bash / zsh:**

```bash
rsync -avh --progress \
  "<cid>@vera2.c3se.chalmers.se:/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-dist-ft/results/" \
  ./results/
```

Key artifacts under `results/`:

- `checkpoints/<run-id>/run_summary.json` — run id, ckpt dir, dataset,
  effective batch size.
- `checkpoints/<run-id>/checkpoint-<step>/` — sharded model + optimizer
  state. With ZeRO-3 / FSDP these are sharded state dicts; use
  `accelerate` or `torch.distributed.checkpoint` to consolidate before
  serving.
- `eval_report.json` — mean perplexity + per-prompt samples from
  `scripts/eval.py`.

## 11. Verification checklist

- [ ] Every `slurm/*.sbatch` has your real `--account=<naiss-id>`.
- [ ] `RESULTS_HOST`, `MODELS_HOST`, `HF_HOME`, `WANDB_DIR` all resolve
      under `/mimer/NOBACKUP/groups/<naiss-id>/...`, not `$HOME`, not
      Cephyr.
- [ ] `ACCELERATE_CONFIG` in `.env` matches a file in
      `configs/accelerate/`.
- [ ] Laptop `pixi run smoke` prints the expected library versions.
- [ ] Cluster smoke sees `cuda_available: true` and one GPU.
- [ ] `squeue -u $USER` showed the real job in `R` state with
      `alvis` partition and `A100:4` GRES.
- [ ] `run_summary.json` has a non-empty `ckpt_dir`.
- [ ] `du -sh` of the checkpoint tree matches expectations (roughly
      30–60 GB per kept checkpoint at 7B).
- [ ] `eval_report.json` has sensible perplexities.

## 12. Troubleshooting

- **OOM** — reduce in order of cost:
  1. Halve `PER_DEVICE_BATCH`, double `GRAD_ACCUM` to preserve
     effective batch.
  2. Switch `ACCELERATE_CONFIG=ds_zero2` → `ds_zero3`.
  3. In `configs/accelerate/ds_zero3.yaml`, set
     `offload_optimizer_device: cpu`.
  4. Last resort: `offload_param_device: cpu` (5–10× slower).
  5. Drop `MAX_SEQ_LEN`.
- **`num_processes` mismatch** — error like
  `num_processes (4) != world_size (2)`. Your
  `configs/accelerate/<cfg>.yaml` and `--gpus-per-node=A100:N` disagree.
  Keep them aligned.
- **`HF_HOME` silently pointed to `$HOME`** — HF will happily download
  15+ GB into your home on first `from_pretrained`, exhausting the
  Cephyr user quota. Always export `HF_HOME` (and
  `TRANSFORMERS_CACHE`) to a Mimer path before any HF call, both in
  `.env` and inside every sbatch.
- **Cephyr quota warnings during training** — `RESULTS_DIR` or a
  DataLoader worker's `/tmp` fallback landed on Cephyr. Check with
  `lfs quota -u $USER /cephyr`. Move offenders to Mimer, restart the
  job.
- **Sharded checkpoints won't load for eval** — ZeRO-3 / FSDP save
  sharded state dicts. `scripts/eval.py` uses plain
  `AutoModelForCausalLM.from_pretrained` which expects a consolidated
  state dict; run
  `accelerate merge-weights <ckpt-dir> <merged-dir>` (or the
  equivalent `torch.distributed.checkpoint.consolidate`) before eval.
- **Job killed at `--time` with no checkpoint** — `SAVE_STEPS` was
  larger than steps completed. Shrink `SAVE_STEPS`, or request a
  longer wall-clock.
- **wandb hangs on first call** — cluster nodes often have no outbound
  HTTPS. Keep `WANDB_MODE=offline`, and `wandb sync` the runs from a
  login node afterwards.
- **`scripts/train.py` rank-0-only output is missing** — the worker
  crashed before reaching the `RANK == 0` print. Check `*.err` for the
  NCCL / DeepSpeed stack trace on the crashing rank.
