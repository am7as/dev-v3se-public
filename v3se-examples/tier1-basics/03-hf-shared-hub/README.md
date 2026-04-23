# `03-hf-shared-hub` — HuggingFace from C3SE's pre-downloaded hub

Load a HuggingFace model in-process, pointing `transformers` at the
read-only HF mirror C3SE maintains at
`/mimer/NOBACKUP/Datasets/LLM/huggingface/hub/`. Zero download, zero
Cephyr/Mimer quota impact — the mirror lives on a shared filesystem
that doesn't count against your allocation.

**Use when**: the model you want is already mirrored by C3SE.
Always check with `ls` first — see step-by-step below.

## Layout

```
03-hf-shared-hub/
├── apptainer/
│   ├── dev.def                     bind-mount + Pixi Python env
│   └── app.def                     baked-code variant
├── configs/config.toml
├── docker-compose.yml              laptop dev mode
├── pixi.toml                       transformers + torch + accelerate
├── pyproject.toml
├── scripts/
│   ├── smoke.py                    prints model + device info
│   ├── info.py
│   └── infer.py                    `pixi run infer --prompt "…"`
├── slurm/
│   ├── cpu-smoke.sbatch
│   └── gpu-t4.sbatch
├── src/hf_shared_hub/
│   ├── model.py                    ONLY loads from HF_MODEL_SNAPSHOT
│   └── config.py
├── tests/test_smoke.py
└── docs/
    ├── setup.md
    └── usage.md                    ← step-by-step walkthrough
```

## One env var you must set

```ini
# .env
HF_MODEL_SNAPSHOT=/mimer/NOBACKUP/Datasets/LLM/huggingface/hub/models--<org>--<name>/snapshots/<hash>/
```

**No fallback to Hub streaming** — if the snapshot path is missing
or wrong, the code raises a clear error telling you where to look.
For Hub-streaming behaviour use `../09-hf-hub-streaming/`. For
baking weights into your own SIF use `../08-hf-sif-bundle/`.

## Quickstart

Run `docs/usage.md` top-to-bottom for the full zero-to-results
walkthrough. One-line summary:

```bash
# Laptop cannot load from /mimer/... — do laptop dev against a
# locally-cached snapshot OR skip laptop HF work and go straight
# to Alvis. See docs/usage.md § "Laptop workaround".

# On Alvis:
ssh <cid>@alvis2.c3se.chalmers.se
cd /cephyr/users/<cid>/Alvis/hf-shared-hub
apptainer build dev.sif apptainer/dev.def
sbatch slurm/gpu-t4.sbatch
```

## What to change to make this yours

1. In `.env`, set `HF_MODEL_SNAPSHOT` to the model you want.
2. In `slurm/gpu-t4.sbatch`, set `#SBATCH --account=<YOUR_NAISS>`.
3. Tweak `scripts/infer.py` to run against your prompts.

## When to leave

- The model isn't in C3SE's mirror → `../08-hf-sif-bundle/` (bake
  your own SIF) or `../09-hf-hub-streaming/` (download on demand).
- Multi-provider routing → `../tier2-combinations/11-multi-provider-inference/`.
- LoRA finetuning → `../05-train-lora/`.
