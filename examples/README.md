# examples

A library of **10 worked, public-shareable example projects** for
Chalmers C3SE's environment (Alvis GPU cluster + Cephyr storage).

Each example is a fully-functional, single-repo project demonstrating
a specific cluster-resource-utilization pattern. Every example runs in
three modes — **local Docker**, **local Apptainer**, **Alvis Apptainer
via Slurm** — with the same code; only env vars differ.

> For **just the scaffold** (one project shape, no worked examples) see
> [`../templates/`](../templates/).

## Pick an example by task

### Tier 1 — Basics (single-target; learn one thing at a time)

| Template                                                                              | What you get                                                                                                  |     |
| ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- | --- |
| [`tier1-basics/01-foundation`](tier1-basics/01-foundation/)                           | The skeleton. Pixi + Docker + Apptainer + Slurm, prints device info. No AI, no data. Start here.              |     |
| [`tier1-basics/02-inference-api-token`](tier1-basics/02-inference-api-token/)         | One LLM via API token (OpenAI default). Simplest "I want to call an LLM".                                     |     |
| [`tier1-basics/03-hf-shared-hub`](tier1-basics/03-hf-shared-hub/)                     | HF model loaded from C3SE's pre-downloaded hub (`/mimer/NOBACKUP/Datasets/LLM/huggingface/hub/`). Zero quota. |     |
| [`tier1-basics/04-data-cephyr`](tier1-basics/04-data-cephyr/)                         | Data workflow on Cephyr: sync, read, write, respect quotas. No AI.                                            |     |
| [`tier1-basics/05-train-lora`](tier1-basics/05-train-lora/)                           | Smallest possible LoRA finetune of a tiny HF model. No distributed training.                                  |     |
| [`tier1-basics/06-lmstudio-cluster-server`](tier1-basics/06-lmstudio-cluster-server/) | Host LM Studio on Alvis via Slurm + SSH port-forward. OpenAI-compatible endpoint.                             |     |
| [`tier1-basics/07-ollama-cluster-server`](tier1-basics/07-ollama-cluster-server/)     | Host Ollama on Alvis via Slurm + SSH port-forward. OpenAI-compatible endpoint.                                |     |
| [`tier1-basics/08-hf-sif-bundle`](tier1-basics/08-hf-sif-bundle/)                     | Clone an HF model once and bake it into a SIF (cluster) / Docker image (laptop).                              |     |
| [`tier1-basics/09-hf-hub-streaming`](tier1-basics/09-hf-hub-streaming/)               | Stream an HF model from the Hub at first call; caches to Mimer project storage.                               |     |

### Tier 2 — Combinations (compose the basics)

| Template | What you get                                                                          |
|----------|---------------------------------------------------------------------------------------|
| [`tier2-combinations/11-multi-provider-inference`](tier2-combinations/11-multi-provider-inference/) | Switch between API token / CLI subscription / vLLM by config change. |
| [`tier2-combinations/12-multi-source-data`](tier2-combinations/12-multi-source-data/) | Switch between local / Cephyr private / Cephyr shared (`/mimer/Datasets`) / HF Hub / GCS by config change. |
| [`tier2-combinations/13-train-infer-pipeline`](tier2-combinations/13-train-infer-pipeline/) | Full LoRA finetune → SIF bundle → inference on the finetuned adapter. |
| [`tier2-combinations/14-git-model-bundle`](tier2-combinations/14-git-model-bundle/) | Git-cloned model weights baked into a SIF (cluster) or Docker image (laptop). |

### Tier 3 — Advanced (production-grade references)

| Template | What you get                                                                      |
|----------|-----------------------------------------------------------------------------------|
| [`tier3-advanced/21-distributed-finetune`](tier3-advanced/21-distributed-finetune/) | 4× A100 DeepSpeed/FSDP full finetune with sharded checkpoints and accelerate. |
| [`tier3-advanced/22-reconstruct-retrain-infer`](tier3-advanced/22-reconstruct-retrain-infer/) | Architecture surgery + full retrain + SIF deployment + eval harness. |

## Cross-cutting reference

Docs in [`docs/`](docs/) that apply to every example:

| Topic | Doc                                                          |
|-------|--------------------------------------------------------------|
| Which template should I pick? | [docs/choosing-a-template.md](docs/choosing-a-template.md) |
| Alvis & Cephyr in 10 minutes  | [docs/c3se-primer.md](docs/c3se-primer.md)             |
| Dev vs deployment containers  | [docs/container-modes.md](docs/container-modes.md)     |
| SSH, rsync, sbatch, OnDemand  | [docs/cluster-workflow.md](docs/cluster-workflow.md)   |
| Data source patterns          | [docs/data-patterns.md](docs/data-patterns.md)         |
| SIF management under quota    | [docs/sif-management.md](docs/sif-management.md)       |
| AI model source catalog       | [docs/ai-model-catalog.md](docs/ai-model-catalog.md)   |

## Shared infrastructure

Every example pulls from [`_shared/`](_shared/) for its baseline:

- **Apptainer recipes** — `_shared/apptainer/base.def` (Pixi + Python 3.12)
- **Dockerfile** — `_shared/docker/Dockerfile.dev`
- **Slurm sbatch templates** — CPU, 1× T4, 1× A100, vLLM server
- **Sync scripts** — `sync-to-cephyr.sh`, `port-forward.sh`, etc.
- **Env template** — `_shared/env/.env.template`

## Quickstart (pick any example)

### PowerShell (Windows)

```powershell
# 1. Copy the example you want into its own project folder
Copy-Item tier1-basics\01-foundation ..\my-new-project -Recurse

# 2. Go there and configure
cd ..\my-new-project
Copy-Item .env.example .env
#    (edit .env: DATA_HOST, MODEL env vars, API keys, Slurm account)

# 3. Run in Docker (laptop dev loop)
docker compose up -d dev
docker compose exec dev pixi run smoke

# 4. Or run as Apptainer (matches Alvis execution)
apptainer build dev.sif apptainer/dev.def
apptainer run --bind .:/workspace dev.sif pixi run smoke

# 5. When ready, rsync to Cephyr and sbatch on Alvis
bash ./_shared/scripts/sync-to-cephyr.sh
ssh <cid>@alvis2.c3se.chalmers.se
cd /cephyr/users/<cid>/Alvis/my-new-project
sbatch slurm/gpu-t4.sbatch
```

### Bash / zsh (macOS / Linux)

```bash
# 1. Copy the example you want into its own project folder
cp -r tier1-basics/01-foundation ../my-new-project

# 2. Go there and configure
cd ../my-new-project
cp .env.example .env
#    (edit .env: DATA_HOST, MODEL env vars, API keys, Slurm account)

# 3. Run in Docker (laptop dev loop)
docker compose up -d dev
docker compose exec dev pixi run smoke

# 4. Or run as Apptainer (matches Alvis execution)
apptainer build dev.sif apptainer/dev.def
apptainer run --bind .:/workspace dev.sif pixi run smoke

# 5. When ready, rsync to Cephyr and sbatch on Alvis
bash ./_shared/scripts/sync-to-cephyr.sh
ssh <cid>@alvis2.c3se.chalmers.se
cd /cephyr/users/<cid>/Alvis/my-new-project
sbatch slurm/gpu-t4.sbatch
```

## Canonical contract

Every example promises:

- **Container paths**: `/workspace`, `/data`, `/results`, `/models` — fixed.
- **Env vars**: `DATA_DIR`, `RESULTS_DIR`, `MODELS_DIR` — fixed names.
- **Pixi tasks**: `smoke`, `info`, `test`, `lint` — present everywhere.
- **No personal info** in any committed file — placeholders only.
- **`.env` gitignored**; only `.env.example` committed.
- **`docker-compose.yml` uses `${DATA_HOST:-../<sibling>}` defaults**.
- **Every sbatch uses `--account=<PROJECT_ID>` placeholder**.

## Related

- [`../templates/`](../templates/) — just the scaffold (one project shape to clone).
