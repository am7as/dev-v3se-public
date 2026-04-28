# Choosing a template

Pick by answering two questions: **what do I want to do** and **how much
infra complexity am I willing to take on right now**.

## By task

| I want to...                                          | Start with                         |
|-------------------------------------------------------|------------------------------------|
| Just set up a C3SE-ready project with nothing fancy   | `01-foundation`                   |
| Call an LLM via an API token (OpenAI/Anthropic/...)   | `02-inference-api-token`          |
| Load a HuggingFace model that C3SE already mirrors (zero download, zero quota) | `03-hf-shared-hub`                |
| Move data to Cephyr / Mimer and process it there      | `04-data-cephyr`                  |
| Finetune a small model with LoRA                      | `05-train-lora`                   |
| Host LM Studio as an HTTP endpoint on a GPU node      | `06-lmstudio-cluster-server`      |
| Host Ollama as an HTTP endpoint on a GPU node         | `07-ollama-cluster-server`        |
| Clone a HuggingFace model once, bake it into a SIF, run offline | `08-hf-sif-bundle`          |
| Stream a HuggingFace model from the Hub on first call | `09-hf-hub-streaming`             |
| Compare multiple LLM providers (API / CLI / vLLM) on the same data | `11-multi-provider-inference` |
| Switch between data on local / Cephyr / Mimer / HF / GCS | `12-multi-source-data`         |
| Finetune → bundle → ship a model as a single SIF      | `13-train-infer-pipeline`         |
| Load a model distributed as a git repo (not HF Hub)   | `14-git-model-bundle`             |
| Multi-GPU full-parameter finetune                     | `21-distributed-finetune`         |
| Change a model's architecture and retrain from scratch | `22-reconstruct-retrain-infer`   |

## By experience level

- **New to C3SE / HPC**: `01-foundation` first. It only covers infra; you
  can swap in your actual science after you've seen it boot cleanly on
  laptop and Alvis.
- **Know HPC, new to C3SE**: skip to whichever Tier 1 matches your task.
  Read [c3se-primer.md](c3se-primer.md) alongside.
- **C3SE power user**: pick a Tier 2 or Tier 3 template, or clone one and
  rewire it.

## Decision tree

```
Do you need AI/ML?
├─ No: process data → 04-data-cephyr / 12-multi-source-data
└─ Yes: Model source?
         ├─ Commercial API (OpenAI, Anthropic, Google, xAI):
         │     02-inference-api-token
         │     → (later) 11-multi-provider-inference to mix providers
         │
         ├─ HuggingFace model, in-process:
         │     Is C3SE mirroring it? (ls /mimer/NOBACKUP/Datasets/LLM/huggingface/hub/)
         │     ├─ Yes, and laptop work is optional:        03-hf-shared-hub
         │     ├─ Reuse across many jobs (bake once):      08-hf-sif-bundle
         │     └─ Iterating fast on laptop, not in mirror: 09-hf-hub-streaming
         │
         ├─ HTTP server on GPU node (OpenAI-compatible):
         │     ├─ vLLM (fastest throughput):  11-multi-provider-inference
         │     ├─ LM Studio (friendly UI):    06-lmstudio-cluster-server
         │     └─ Ollama (pull/run catalog):  07-ollama-cluster-server
         │
         └─ Model ships as a git repo (not HF Hub):
               14-git-model-bundle
         ┊
         Training?
         ├─ No:          stay in the inference template you picked above.
         ├─ LoRA / PEFT only:   05-train-lora
         │                      → (later) 13-train-infer-pipeline to wrap with inference
         └─ Full-parameter:     21-distributed-finetune (4× A100 DeepSpeed / FSDP)
                                → 22-reconstruct-retrain-infer for architecture surgery
```

## By storage pattern

If you already know what data layout you want, route by that instead:

| My data / model lives on...                          | Start with                         |
|------------------------------------------------------|------------------------------------|
| My laptop, small                                     | `01-foundation` or `04-data-cephyr` (Pattern 1 / local) |
| Cephyr (small, code-adjacent)                        | `04-data-cephyr` (Pattern 3)       |
| Mimer project allocation (big, writable)             | `04-data-cephyr` (Pattern 4) + `12-multi-source-data` |
| Mimer shared (C3SE-mirrored read-only)               | `04-data-cephyr` (Pattern 5) + `12-multi-source-data` |
| HuggingFace Hub                                      | `09-hf-hub-streaming`              |
| Pre-mirrored HF on C3SE                              | `03-hf-shared-hub`                 |
| Baked into a SIF (reproducible, offline)             | `08-hf-sif-bundle`                 |
| A git repo with weights                              | `14-git-model-bundle`              |

## By AI-utilization method

For a full comparison with pros/cons/quotas per method, see
[ai-methods-comparison.md](ai-methods-comparison.md). The same 11 rows
are here, one-to-one with a template:

| # | Method                                           | Template                          |
|---|--------------------------------------------------|-----------------------------------|
| 1 | API token                                        | `02-inference-api-token`, `11-multi-provider-inference` |
| 2 | CLI subscription (Claude / Gemini CLI)           | `11-multi-provider-inference` (`claude_cli` provider) |
| 3 | LM Studio on cluster                             | `06-lmstudio-cluster-server`      |
| 4 | Ollama on cluster                                | `07-ollama-cluster-server`        |
| 5 | vLLM server on cluster                           | `11-multi-provider-inference`     |
| 6a | HF in-process — from C3SE shared hub            | `03-hf-shared-hub`                |
| 6b | HF in-process — clone + bundle into SIF         | `08-hf-sif-bundle`                |
| 6c | HF in-process — streaming from Hub              | `09-hf-hub-streaming`             |
| 7 | Git-cloned model repo → SIF / Docker             | `14-git-model-bundle`             |
| 8 | Fine-tuning — LoRA / PEFT                        | `05-train-lora`, `13-train-infer-pipeline` |
| 9 | Fine-tuning — full / distributed                 | `21-distributed-finetune`, `22-reconstruct-retrain-infer` |

## What every template gives you

Regardless of which you pick, you get:

- **Pixi** dependency management inside the container.
- **`.env`-driven** paths and credentials (no hard-coded host paths in
  any committed file).
- **Docker Compose** for laptop dev (code mounted, not baked in).
- **Apptainer** recipes for both laptop and Alvis.
- **Slurm sbatch** scripts tuned for C3SE partitions, with
  `--account=<PROJECT_ID>` placeholder.
- **Sync scripts** for Cephyr (`sync-to-cephyr.sh`) and Mimer
  (`sync-to-mimer.sh`).
- **`docs/`** folder with `setup`, `usage`, `modification`, `structure`,
  `troubleshooting`.
- **Smoke test** (`pixi run smoke`) that exercises the golden path.
- **Canonical env vars**: `CEPHYR_USER`, `CEPHYR_PROJECT_PATH`,
  `MIMER_GROUP_PATH`, `MIMER_PROJECT_PATH`, `ALVIS_ACCOUNT`,
  `CEPHYR_TRANSFER_HOST`, `ALVIS_LOGIN_HOST`.

## Adapting a template

All templates are meant to be **copied, not forked**. Clone the whole
tier folder, rename, start editing. The structural conventions
(filenames, env vars, `pixi run <task>` names, `/data` + `/results` +
`/models` container paths) should **not** drift — that's what makes
templates interchangeable.

See each template's `docs/modification.md` for the boundaries of what
you can safely change without breaking the cluster story.
