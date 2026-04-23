# `21-distributed-finetune` — multi-GPU full-parameter finetune

Production-grade reference for full-parameter finetuning on Alvis A100s
using `accelerate` + DeepSpeed (ZeRO-2/3) or FSDP. Designed around a
real-world use case: you have a 7B–13B model, a meaningful dataset, and
want to train seriously — not just experiment.

## What's new vs Tier 2

- `configs/accelerate/ds_zero2.yaml`, `ds_zero3.yaml`, `fsdp.yaml` —
  hand-tuned `accelerate` configs for Alvis A100 nodes.
- `src/dist_ft/train.py` — distributed training loop using
  `accelerate.Accelerator` + `trl.SFTTrainer`.
- `slurm/train-a100x4.sbatch` — 4× A100, 24h, checkpoints to
  `$RESULTS_DIR/checkpoints/<run-id>/`.
- Sharded checkpoint save/load that works across node restarts.
- Eval harness that runs at the end of training.

## Model / compute budget

| Model size | GPUs           | Strategy                | Approximate time/epoch |
|------------|----------------|-------------------------|-----------------------|
| 1B         | 1× T4          | fp16 single GPU         | 10 min (small data)   |
| 7B         | 4× A100 40 GB  | DeepSpeed ZeRO-2 bf16  | 2-4 h (alpaca-52k)    |
| 13B        | 4× A100 80 GB  | DeepSpeed ZeRO-3 bf16  | 4-8 h                 |
| 70B+       | 8+× A100       | FSDP + CPU offload     | Days                  |

## Quickstart

```powershell
# Laptop: read the code, adjust configs, smoke test
docker compose up -d dev
docker compose exec dev pixi install
docker compose exec dev pixi run smoke
```

Training this on a laptop is not the point. On Alvis:

```bash
ssh alvis
cd /cephyr/users/$USER/Alvis/dist-ft
apptainer build dev.sif apptainer/dev.def
# Edit slurm/train-a100x4.sbatch for your --account + HF_MODEL + HF_DATASET
sbatch slurm/train-a100x4.sbatch
```

## When to leave

- Need to modify the model architecture itself → `22-reconstruct-retrain-infer`.
- Just need LoRA, not full-param → `13-train-infer-pipeline`.
