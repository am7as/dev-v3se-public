# `05-train-lora` — smallest possible LoRA finetune

Extends `01-foundation` with a minimal PEFT/LoRA training loop. Runs end-
to-end on a T4 in a few minutes.

## What's new vs foundation

- `src/train_lora/train.py` — the training loop.
- `scripts/train.py` — `pixi run train` entrypoint.
- `scripts/infer.py` — `pixi run infer --adapter-dir ...` loads the
  adapter and generates text.
- `pixi.toml` adds `transformers`, `peft`, `datasets`, `trl`, `accelerate`.
- `.env.example` adds `HF_MODEL`, `HF_DATASET`, `LORA_R`, `NUM_EPOCHS`.

## Defaults (small on purpose)

- **Model**: `sshleifer/tiny-gpt2` — 8 MB. Runs on CPU in seconds.
- **Dataset**: a tiny in-memory list (5 rows). No download.
- **LoRA r=8, alpha=16**. Standard sane defaults.
- **1 epoch, batch 4**. Finishes in under a minute on T4.

This is a skeleton. Swap to a real model/dataset in `.env` once the loop
works.

## Quickstart

```powershell
Copy-Item . ..\my-project -Recurse
cd ..\my-project
Copy-Item .env.example .env
docker compose up -d dev
docker compose exec dev pixi install

# Train (outputs to $RESULTS_DIR/adapters/<timestamp>/)
docker compose exec dev pixi run train

# Use the adapter
docker compose exec dev pixi run infer --adapter-dir /results/adapters/<ts>/ --prompt "Once upon a time"
```

## When to leave

- Distributed training → `21-distributed-finetune`.
- Finetune + deploy as a single SIF → `13-train-infer-pipeline`.
- Architecture modification → `22-reconstruct-retrain-infer`.
