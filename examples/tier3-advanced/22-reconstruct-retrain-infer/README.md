# `22-reconstruct-retrain-infer` — model architecture surgery

The most complete reference template. Demonstrates the full cycle:

1. **Reconstruct**: take a pretrained HF model, modify its architecture
   (replace the head, add a classifier layer, swap attention module,
   inject adapters at specific layers).
2. **Retrain**: train the modified model end-to-end with the distributed
   setup from `21-distributed-finetune`.
3. **Infer**: deploy the retrained model as a self-contained SIF and run
   inference.
4. **Evaluate**: quantitative evaluation against a held-out set.

Use this when LoRA isn't enough because you're changing the model's
capabilities (e.g., adding a regression head for continuous outputs, or
inserting retrieval slots between layers).

## What's new vs `21`

- `src/reco/surgery.py` — the architecture modification logic (swap
  layers, add heads). Keep this small; the skeleton here demonstrates
  "add a classification head"; your real project substitutes your
  surgery.
- `src/reco/evaluate.py` — evaluation harness with metrics.
- `configs/surgery.yaml` — declarative "which layers to touch".

## The surgical example

The shipped example swaps an LLM's LM head with a 5-way classification
head. This is the simplest architecture change that still exercises:
loading pretrained weights, freezing/unfreezing selected params,
retraining with a different loss, evaluating with classification metrics.

Substitute your actual surgery — the infrastructure around it (SIF,
sbatch, eval) stays.

## Quickstart

```powershell
docker compose up -d dev
docker compose exec dev pixi install
docker compose exec dev pixi run smoke     # import checks only
```

On Alvis (real training):

```bash
ssh alvis
cd /cephyr/users/$USER/Alvis/reco
apptainer build dev.sif apptainer/dev.def

# 1) Surgery (creates results/surgeried/<ts>/ — the modified model)
sbatch slurm/surgery.sbatch

# 2) Retrain
sbatch --export=ALL,MODEL=/cephyr/.../results/surgeried/<ts> slurm/train.sbatch

# 3) Evaluate
sbatch --export=ALL,CKPT=/cephyr/.../results/checkpoints/<run> slurm/eval.sbatch

# 4) Bundle for deployment
sbatch --export=ALL,CKPT=/cephyr/.../results/checkpoints/<run> slurm/bundle.sbatch
```

## This is the end of the template library.

If you've outgrown this template, you're writing a custom training
framework. Consider contributing back a new template.
