# AI model catalog — which source, which template, which cluster story

Map from "where is my model coming from" → "which template should I
clone" → "how does that actually run on Alvis".

## The seven sources

### 1. API token (premium, commercial)

- **Examples**: OpenAI GPT-4, Anthropic Claude, Google Gemini, xAI Grok.
- **How**: Python SDK + API key in env var. Outbound HTTPS from compute node.
- **Laptop**: works out of the box.
- **Alvis**: works out of the box (compute nodes have outbound HTTPS).
- **Template**: `02-inference-api-token` → `11-multi-provider-inference`.

### 2. CLI subscription (premium)

- **Examples**: Claude CLI (Claude Pro/Max), Gemini CLI.
- **How**: call the CLI as a subprocess from Python. Credentials live
  in a host directory (e.g., `~/.claude/`).
- **Laptop**: log in once on host, bind-mount the credential dir into container.
- **Alvis**: copy credential dir to Cephyr, bind it in your sbatch.
  Credentials may need periodic refresh if subscription requires
  browser-auth (check provider).
- **Template**: `11-multi-provider-inference` (includes CLI path).

### 3. LM Studio (open-weight, laptop server)

- **Examples**: any HF GGUF model.
- **How**: run LM Studio on host, it exposes an OpenAI-compatible endpoint.
- **Laptop**: excellent. Fast iteration, swap models in GUI.
- **Alvis**: **not recommended by C3SE** (no auth, model-dir bloat).
  Use vLLM pattern instead.
- **Template**: `11-multi-provider-inference` (laptop-only mode). Not in
  cluster-only templates.

### 4. Ollama (open-weight, laptop server)

- Same story as LM Studio. Laptop only. On Alvis, use vLLM.
- **Template**: `11-multi-provider-inference` (laptop mode).

### 5. vLLM (open-weight, cluster server)

- **How**: start vLLM as a Slurm-launched OpenAI-compatible server on a
  GPU node; client code connects to `localhost:<port>` inside the same
  allocation, or port-forwards to laptop.
- **Laptop**: runs but mostly unnecessary — use LM Studio/Ollama instead.
- **Alvis**: the sanctioned pattern. `_shared/apptainer/vllm.def` +
  `_shared/slurm/vllm-server.sbatch` + `find_ports` pattern.
- **Template**: `11-multi-provider-inference`.

### 6. Direct HF Transformers load (in-process)

- **Examples**: any HF model you load via `AutoModel.from_pretrained()`.
- **How**: model weights are a file tree. Loaded into process memory.
- **Laptop**: fine if you have a GPU and the model fits.
- **Alvis**: **prefer the pre-downloaded snapshot** at
  `/mimer/NOBACKUP/Datasets/LLM/huggingface/hub/` when available. Fall
  back to `HF_HOME` in project storage (NOT `$HOME`).
- **Template**: `03-hf-shared-hub`.

### 7. Git-cloned model repo

- **Examples**: research models not on HF Hub; custom checkpoints.
- **How**: `git clone https://github.com/org/model` then load.
- **Laptop**: just clone.
- **Alvis**: clone to `/mimer` (bigger, higher file-count allowance),
  then bake into a SIF per [sif-management.md](sif-management.md).
- **Template**: `03-hf-shared-hub` (adaptable) or `22-reconstruct-retrain-infer`.

## Decision: which source for which need

| I want to…                                              | Pick…                   |
|---------------------------------------------------------|-------------------------|
| Compare multiple frontier LLMs cheaply                  | 1 (token)               |
| Use my Claude Max subscription inside batch jobs        | 2 (CLI)                 |
| Fast local prototyping with Gemma / Llama               | 3 (LM Studio) or 4 (Ollama) |
| Serve an open LLM at scale for hundreds of prompts      | 5 (vLLM)                |
| Load an open LLM for custom logic (e.g., token probs)   | 6 (HF Transformers)     |
| Use a research model that isn't on HF Hub               | 7 (git clone)           |

## Cluster performance cheat sheet

| Source  | Latency  | Throughput | Cluster fit    |
|---------|----------|------------|----------------|
| API     | ~500 ms  | ~100 RPS (rate-limited) | **Good** |
| CLI     | 1–5 s    | 1 RPS      | Okay (subprocess overhead) |
| LM Studio | 50–500 ms | Medium | **Not recommended** |
| Ollama  | 50–500 ms | Medium     | **Not recommended** |
| vLLM    | 20–200 ms | **High**   | **Excellent** |
| HF load | 100–2000 ms | Low    | **Good** (for custom use cases) |

## Credentials: where each lives

| Source   | Credential                  | Laptop home       | Alvis home                      |
|----------|-----------------------------|-------------------|----------------------------------|
| API      | env var in `.env`           | `.env`            | `.env` (synced separately, not via rsync) |
| Claude CLI | `~/.claude/` + `~/.claude.json` | bind-mounted | bind-mounted from Cephyr |
| HF Hub (private models) | `HF_TOKEN` env var | `.env`    | `.env`                           |
| WandB (for training)    | `WANDB_API_KEY` env var | `.env` | `.env`                       |

## Never commit

API keys, CLI credentials, or any file under `~/.claude/`, `~/.ollama/`,
`~/.gemini/`. All templates' `.gitignore` excludes `.env` — keep it that
way.
