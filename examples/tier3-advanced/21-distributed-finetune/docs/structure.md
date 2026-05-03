# `21-distributed-finetune` — folder layout

```
21-distributed-finetune/
├── README.md                   why-this-template + quickstart
├── .env.example                env vars + training + tracking config
├── .gitignore
├── docker-compose.yml          laptop dev stack (no GPU by default)
├── pixi.toml                   pixi tasks + deps (torch, accelerate, deepspeed, trl)
├── pyproject.toml              Python packaging + wheel target
├── apptainer/
│   ├── dev.def                 dev SIF (code bind-mounted in) — laptop + Alvis
│   └── app.def                 deployment SIF (code baked in)
├── configs/
│   └── accelerate/
│       ├── ds_zero2.yaml       DeepSpeed ZeRO-2 — fastest, model fits per-GPU
│       ├── ds_zero3.yaml       DeepSpeed ZeRO-3 — params sharded, bigger models
│       └── fsdp.yaml           FSDP (PyTorch-native) — alt to ZeRO-3
├── scripts/                    entrypoints for `pixi run <task>`
│   ├── smoke.py                pixi run smoke   — offline, asserts imports
│   ├── info.py                 pixi run info    — prints resolved env
│   ├── train.py                accelerate-launched distributed SFT
│   └── eval.py                 pixi run eval    — checkpoint shape-detection + eval
├── src/dist_ft/
│   ├── __init__.py
│   ├── config.py               path + training-hyperparam env resolver
│   └── train.py                core: TRL SFTTrainer with accelerate orchestration
├── slurm/
│   ├── train-a100x4.sbatch     4× A100 full-parameter training (24 h / 256 G)
│   └── eval-a100.sbatch        1× A100 eval against a saved checkpoint
├── tests/
│   └── test_smoke.py           pytest — config + import smoke
└── docs/
    ├── setup.md                first-time setup (laptop + Alvis A100 access)
    ├── usage.md                full-pipeline walkthrough (train + eval)
    ├── modification.md         how to swap model / dataset / parallelism strategy
    ├── structure.md            (this file)
    └── troubleshooting.md      per-strategy failure modes
```

## Key files, one paragraph each

### `apptainer/dev.def` and `apptainer/app.def`

Pixi-based containers. The pixi env is substantial (torch+cu121,
accelerate, deepspeed, trl, wandb) — SIF builds take ~10 min.
DeepSpeed specifically needs CUDA + NCCL at runtime, but the SIF
itself builds fine on a CPU login node because DeepSpeed's JIT-
compiled kernels are built on first `accelerate launch`, not at SIF
build.

### `apptainer/` — no `bundle.def`

Unlike `13-train-infer-pipeline`, this template doesn't ship a
bundle template. The deliverable is a **checkpoint directory**, not
a self-contained SIF. Use `13` as a starting point if you need to
bundle a full-parameter checkpoint into a deployable SIF.

### `configs/accelerate/ds_zero2.yaml`

DeepSpeed ZeRO-2: optimizer states + gradients partitioned across
GPUs; full model weights stay on each GPU. Fastest strategy when the
model fits (7-9B params on 4× A100 40 GB). `num_processes: 4` matches
`--gpus-per-node=A100:4` in the sbatch.

### `configs/accelerate/ds_zero3.yaml`

DeepSpeed ZeRO-3: parameters also partitioned. Slower than ZeRO-2
but fits much larger models (34–70B). `offload_optimizer_device` /
`offload_param_device` are `none` by default; set them to `cpu` as
OOM escape hatches (with heavy speed cost).

### `configs/accelerate/fsdp.yaml`

PyTorch-native Fully Sharded Data Parallel. Similar to ZeRO-3;
sometimes preferred by teams avoiding DeepSpeed-specific tooling.
Uses `SHARDED_STATE_DICT` — eval needs extra consolidation (see
`scripts/eval.py`).

### `slurm/train-a100x4.sbatch`

24-hour `A100:4` job (`--cpus-per-task=16`, `--mem=256G`). Sources
`.env`, defaults `RESULTS_DIR` + `HF_HOME` to `$PWD/...` — **this
default is safe on laptop only**; on Alvis the values **must** be
overridden in `.env` to point at Mimer (see storage section).
Launches:

```bash
apptainer run --nv --bind .:/workspace "$SIF" \
    accelerate launch --config_file "configs/accelerate/${CFG}.yaml" scripts/train.py
```

where `CFG=${ACCELERATE_CONFIG:-ds_zero2}`. `--account=<PROJECT_ID>`
placeholder must be replaced.

### `slurm/eval-a100.sbatch`

1-hour `A100:1`. Takes `CKPT=/path/to/checkpoint` via `--export`.
Runs `pixi run eval --ckpt-dir "$CKPT"` — the eval script auto-detects
ZeRO-3 / FSDP / standard HF shapes and consolidates when needed.

### `src/dist_ft/config.py`

Env resolver. Exposes distributed-training knobs:
`per_device_batch()`, `grad_accum()`, `max_seq_len()`, `warmup_ratio()`,
`save_steps()`, `save_total_limit()`, plus the usual path helpers.
`effective_bs = per_device_batch × grad_accum × WORLD_SIZE` is
computed in `train.py`.

### `src/dist_ft/train.py`

The heart. Uses TRL's `SFTTrainer`. Loads the full base model
(`torch_dtype=torch.bfloat16`), loads the HF dataset, applies
Alpaca-style row formatting (override `_format_row` for other
schemas), trains via `SFTConfig` with `gradient_checkpointing=True`,
`bf16=True`. `accelerate launch` handles ZeRO / FSDP orchestration;
the training loop is written as if single-GPU. Rank-0 writes
`run_summary.json`; other ranks skip.

### `scripts/train.py`

Thin CLI — calls `dist_ft.train.run()`, prints only on rank 0.
Invoked as `accelerate launch --config_file … scripts/train.py`.

### `scripts/eval.py`

Checkpoint-shape-aware eval. Detects three layouts:
- **Standard HF** (`config.json` + `model.safetensors` or sharded index)
  → loaded directly.
- **DeepSpeed ZeRO-3** (`global_step*/mp_rank_*_model_states.pt`) →
  consolidated via `zero_to_fp32.py` into a sibling
  `<ckpt>.consolidated/` dir before loading.
- **FSDP sharded** (`*.safetensors` shards without an index) →
  consolidated via `accelerate merge-weights`.

Writes `$RESULTS_DIR/eval_report.json` with per-prompt generation +
perplexity + mean PPL.

### `docker-compose.yml`

Laptop dev stack. Identical shape to `05-train-lora`: bind-mount
project, `$DATA_HOST` / `$RESULTS_HOST` / `$MODELS_HOST`, pixi-env
volume. GPU stanza not enabled by default — distributed training
doesn't practically run on laptop; docker-compose is for code
iteration, not training.

### `tests/test_smoke.py`

Asserts config defaults, `accelerate` + `deepspeed` + `trl` import.
Does not train. < 1 s.

## Storage model — the template with the biggest appetite

Full-parameter finetuning is the most storage-hungry workflow in the
library:

| Artefact                | Size per item   | Frequency          | Tier             |
|-------------------------|-----------------|---------------------|------------------|
| Base model snapshot     | 16–140 GB       | Once per model      | **Mimer project** (`$HF_HOME`) |
| Checkpoint (ZeRO-2)     | 16–32 GB        | Every `SAVE_STEPS`  | **Mimer project** (`$RESULTS_DIR/checkpoints/<ts>/`) |
| Checkpoint (ZeRO-3)     | same, sharded   | Every `SAVE_STEPS`  | **Mimer project**  |
| Checkpoint (FSDP)       | same, sharded   | Every `SAVE_STEPS`  | **Mimer project**  |
| Eval consolidated dir   | = base model    | Once per checkpoint | **Mimer project**  |
| Eval report JSON        | KB              | Once per eval       | **Mimer project**  |

`SAVE_TOTAL_LIMIT=3` caps how many checkpoints live on disk — but
even 3 checkpoints of a 9B bf16 model is ~50 GB. This will not fit
on Cephyr. Full stop.

### Canonical bind mounts

| Container path | Laptop host                      | Alvis host                                        | Storage tier                |
|----------------|----------------------------------|---------------------------------------------------|-----------------------------|
| `/workspace`   | `.`                              | `/cephyr/users/<cid>/Alvis/<project>/`            | **Cephyr** — code + SIF     |
| `/data`        | `${DATA_HOST:-../data}`          | `/mimer/NOBACKUP/groups/<naiss-id>/data/`         | **Mimer project**           |
| `/results`     | `${RESULTS_HOST:-../results}`    | `$MIMER_USER_DIR/results/`                    | **Mimer project** — `checkpoints/<ts>/` |
| `/models`      | `${MODELS_HOST:-../models}`      | `/mimer/NOBACKUP/groups/<naiss-id>/models/`       | **Mimer project**           |
| `$HF_HOME`     | `/workspace/.hf-cache`           | `$MIMER_USER_DIR/.hf-cache`                   | **Mimer project**           |

### Runtime-vs-build resolution

- **Build time**: no weights baked. Pixi env + system tools only.
- **Compose up** (laptop): `.env` drives binds. Training doesn't run
  here in practice — laptop lacks A100s.
- **Train sbatch submit** (Alvis): **the sbatch's defaults
  (`RESULTS_DIR=$PWD/results`, `HF_HOME=$PWD/.hf-cache`) are WRONG
  for Alvis**. The sbatch currently trusts `.env` to override them.
  Before first submission, set both explicitly in `.env`:
  ```
  RESULTS_DIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/results
  HF_HOME=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/.hf-cache
  ```
  Unlike `05` and `13`, this sbatch does **not** branch on
  `MIMER_USER_DIR` — a known inconsistency; track in the
  library-audit checklist.
- **Eval sbatch submit** (Alvis): reads checkpoints from Mimer,
  writes `eval_report.json` to `$RESULTS_DIR` (Mimer).
- **Accelerate config loading**: `accelerate launch --config_file
  configs/accelerate/<cfg>.yaml` — the config file lives on Cephyr
  as part of the code.

### Checkpoint shape matters for consolidation

ZeRO-3 and FSDP write **sharded** checkpoints by default. The
sharded directory is itself ~16 GB on Mimer; consolidating to a
loadable HF tree produces a second ~16 GB copy in
`<ckpt>.consolidated/`. `scripts/eval.py` caches the consolidated
copy and re-uses it on repeat evals — it lives on Mimer, next to
the original checkpoint.

## Design invariants

- **Distributed training is orchestrated by `accelerate`, not by
  Python.** Swap ZeRO-2 / ZeRO-3 / FSDP by changing `ACCELERATE_CONFIG`
  in `.env`; the training loop stays identical.
- **Rank 0 writes, other ranks skip.** `run_summary.json` + any
  user-facing prints are guarded by `int(os.environ["RANK"]) == 0`.
- **Checkpoints live on Mimer, always.** `SAVE_TOTAL_LIMIT=3` caps
  the count but not the individual size.
- **Eval consolidation is lazy and cached.** First eval materialises
  `<ckpt>.consolidated/`; subsequent evals reuse it.
- **`HF_HOME` must be Mimer on Alvis.** The `.env.example` default
  of `/workspace/.hf-cache` is a laptop-only fallback — override in
  `.env` before submitting on Alvis.
