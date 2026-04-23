# `09-hf-hub-streaming` — stream a HuggingFace model from the Hub

The simplest HuggingFace pattern: `from_pretrained(HF_MODEL)` lets
`transformers` download the weights into `HF_HOME` on first call
and reuse them from cache afterwards.

**Use when**: you're iterating rapidly, haven't baked a SIF yet,
and don't mind the first-run download cost. Also what you'll use on
laptop during development.

**Critical caveat on cluster**: `HF_HOME` MUST point at Mimer project
storage (or `/tmp/` for ephemeral jobs). The default `~/.cache/huggingface/`
is under Cephyr and will blow the 60,000-file quota on anything
non-trivial.

## Two env vars

```ini
# .env
HF_MODEL=google/gemma-2-2b-it                                # repo id
HF_HOME=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/.hf-cache    # cluster: Mimer
# HF_HOME=/workspace/.hf-cache                                # laptop: anywhere
HF_TOKEN=                                                     # only for gated models
```

## Quickstart

```bash
# Laptop
Copy-Item .env.example .env     # PowerShell
cp .env.example .env            # bash
docker compose up -d dev
docker compose exec dev pixi install
docker compose exec dev pixi run infer --prompt "Hello"
# First run downloads the model (~5 GB for gemma-2-2b); cached afterwards.

# Cluster
ssh alvis
cd /cephyr/users/<cid>/Alvis/my-hf-streaming
apptainer build dev.sif apptainer/dev.def
sbatch slurm/gpu-t4.sbatch
```

Full walkthrough in [`docs/usage.md`](docs/usage.md).

## Compared to 03 and 08

| Aspect                | 03-hf-shared-hub | 08-hf-sif-bundle | 09-hf-hub-streaming (this) |
|-----------------------|------------------|------------------|----------------------------|
| Network needed at run | no               | no               | yes (first call)           |
| Download every job?   | no               | no               | only until cache warms     |
| Works for any model?  | C3SE-mirrored only | yes            | yes                        |
| Build-time step?      | none             | bake a SIF       | none                       |
| Quota risk on cluster | none             | one SIF file     | **high if `HF_HOME` misconfigured** |
| Best for              | C3SE-provided models | heavy reuse, reproducibility | laptop dev, ad-hoc jobs |

## What to change to make this yours

1. In `.env`, set `HF_MODEL` and (cluster) `HF_HOME` to a Mimer path.
2. In `slurm/gpu-t4.sbatch`, set `#SBATCH --account=<YOUR_NAISS>`
   and verify the `HF_HOME` export line.
3. If the model is gated, set `HF_TOKEN` in `.env`.

## When to leave

- Model IS in C3SE's mirror → `../03-hf-shared-hub/` (zero download).
- Will reuse the model across many jobs → `../08-hf-sif-bundle/`
  (bake once, use forever).
- Need LoRA on top → `../05-train-lora/`.
