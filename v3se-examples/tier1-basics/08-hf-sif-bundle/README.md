# `08-hf-sif-bundle` — clone a HuggingFace model and bake it into a SIF

Download the model weights from HuggingFace **once** at build time,
bake them inside an Apptainer `.sif`, and run the same SIF on laptop
or cluster. No Hub access at run time, one file on Cephyr, fully
reproducible.

**Use when**: the model isn't in C3SE's shared hub (→ can't use 03)
AND you'll reuse it across many jobs (→ streaming-from-Hub each time
is wasteful).

## Layout

```
08-hf-sif-bundle/
├── apptainer/
│   ├── dev.def                     laptop dev (Pixi env, no model)
│   ├── app.def                     deployment variant (baked code)
│   └── model.def                   ← downloads + bakes HF weights at build time
├── docker-compose.yml              laptop dev mode
├── pixi.toml                       transformers + torch + accelerate
├── pyproject.toml
├── scripts/
│   ├── build-model-sif.sh          ← wraps `apptainer build` with HF_MODEL arg
│   ├── smoke.py
│   ├── info.py
│   └── infer.py
├── slurm/
│   ├── cpu-smoke.sbatch
│   └── gpu-t4.sbatch               runs model.sif
├── src/hf_sif_bundle/
│   ├── model.py                    loads from /opt/model (baked path)
│   └── config.py
└── docs/
    ├── setup.md
    └── usage.md                    ← step-by-step walkthrough
```

## Two env vars

```ini
# .env
HF_MODEL=google/gemma-2-2b-it      # any public HF repo
HF_TOKEN=                          # set ONLY for gated models
```

## Quickstart

One line summary:

```bash
# Build — laptop or cluster login node
bash scripts/build-model-sif.sh   # produces ./model.sif

# Run — laptop or cluster
apptainer run --nv model.sif "Hello"                  # laptop (GPU optional)
sbatch slurm/gpu-t4.sbatch                            # cluster (submits a T4 job)
```

Full walkthrough in [`docs/usage.md`](docs/usage.md).

## What to change to make this yours

1. In `.env`, set `HF_MODEL` (and `HF_TOKEN` if gated).
2. In `slurm/gpu-t4.sbatch`, set `#SBATCH --account=<YOUR_NAISS>`.
3. Rename `src/hf_sif_bundle/` to `src/<your_pkg>/` (optional).

## When to leave

- Model IS in C3SE's mirror → `../03-hf-shared-hub/` (zero-build).
- Don't want to bake a SIF, happy to re-download each run →
  `../09-hf-hub-streaming/`.
- Need LoRA finetuning on top → `../05-train-lora/`.
- Need multi-provider routing → `../tier2-combinations/11-multi-provider-inference/`.
