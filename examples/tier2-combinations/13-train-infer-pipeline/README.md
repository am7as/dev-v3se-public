# `13-train-infer-pipeline` — finetune → bundle → deploy

Composes `05-train-lora` with a deploy step: the trained adapter gets
packaged into a portable Apptainer SIF together with the base-model
reference. End result: one file you can hand a collaborator to reproduce
the inference exactly.

## The loop

```
┌───────────────┐   pixi run train    ┌──────────────────┐
│  base model   │ ──────────────────> │   LoRA adapter   │
│  + dataset    │                     │   (~few MB)       │
└───────────────┘                     └──────────────────┘
                                              │
                                              ▼
                                     pixi run bundle
                                              │
                                              ▼
                                     ┌──────────────────┐
                                     │  project.sif     │
                                     │  (deploy-ready)  │
                                     └──────────────────┘
                                              │
                                              ▼
                                     pixi run infer --adapter-dir /opt/adapter
```

## What's new vs Tier 1

- `scripts/bundle.py` — build an Apptainer SIF that packs the adapter,
  the base-model snapshot reference, and the inference code together.
- `apptainer/bundle.def.tpl` — template def file (injected at bundle time).
- WandB + MLflow hooks (opt-in via `.env`).

## Quickstart

```powershell
Copy-Item . ..\my-project -Recurse
cd ..\my-project
Copy-Item .env.example .env
docker compose up -d dev
docker compose exec dev pixi install

# 1) Train
docker compose exec dev pixi run train

# 2) Bundle (produces results/bundles/<ts>.sif)
docker compose exec dev pixi run bundle --adapter-dir /results/adapters/<ts>

# 3) Inference — against the bundled SIF (on Alvis, anywhere)
apptainer run --nv results/bundles/<ts>.sif --prompt "hi"
```

## On Alvis

```bash
sbatch slurm/train-t4.sbatch           # finetune
# after it finishes, note the adapter_dir in the .out file
sbatch --export=ALL,ADAPTER=/cephyr/.../adapters/<ts> slurm/bundle.sbatch
sbatch --export=ALL,BUNDLE=/cephyr/.../bundles/<ts>.sif slurm/infer.sbatch
```

## When to leave

- Bigger models / multi-GPU → `21-distributed-finetune`.
- Modified architecture (not just LoRA) → `22-reconstruct-retrain-infer`.
