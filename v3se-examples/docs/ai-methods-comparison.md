# AI utilization methods — comparison

Side-by-side comparison of every AI-utilization method used in this
library, grouped by where it runs and whether it's C3SE-sanctioned on
the cluster. Use this as the "which example should I start from"
cheat-sheet; each row maps to a concrete tier example.

## Legend

- **Local** / **Cluster**: ✓ works, × n/a or unsupported.
- **Sanctioned** (cluster): ★ preferred, ✓ allowed, ⚠ allowed but
  usually the wrong choice (e.g. burning GPU allocation on HTTPS
  calls).
- **Container**: SIF runs on both laptop and cluster; Docker images
  run on laptop only — so cluster-side, the only container is SIF.

## Unified comparison

| # | Method | Auth | Local | Cluster | Sanctioned | Note — local machine | Note — cluster | Example |
|---|--------|------|:-----:|:-------:|:---------:|----------------------|----------------|---------|
| 1 | **API token** (OpenAI, Anthropic, Google, xAI) | `*_API_KEY` in `.env` | ✓ | ✓ | ⚠ | HTTPS outbound from bare Python, Docker, or SIF — all equivalent | Works but wastes GPU allocation; fire from login node or CPU-only sbatch | [`tier1-basics/02-inference-api-token`](../tier1-basics/02-inference-api-token/) + `tier2-combinations/11-multi-provider-inference` |
| 2 | **CLI subscription** (Claude CLI, Gemini CLI) | interactive OAuth → `~/.claude/` etc. | ✓ | ✓ | ⚠ | Auth must happen here (browser); call from bare host or bind `~/.claude/` into Docker / SIF | Bundle CLI into SIF + bind-mount creds from host; same GPU-waste concern | [`tier2-combinations/11-multi-provider-inference`](../tier2-combinations/11-multi-provider-inference/) (`providers/claude_cli.py`) |
| 3 | **LM Studio** | local GUI account | ✓ | ✓ | ✓ | Native app or behind LAN; its server is OpenAI-compatible | Run `lms server` inside a Slurm job; port-forward to laptop via `_shared/scripts/port-forward.sh`; cache on Mimer | [`tier1-basics/06-lmstudio-cluster-server`](../tier1-basics/06-lmstudio-cluster-server/) |
| 4 | **Ollama** | local CLI | ✓ | ✓ | ✓ | `ollama serve` + `ollama pull`; model cache → any disk | Run `ollama serve` in a Slurm job; port-forward; point `OLLAMA_MODELS` at Mimer (never `~/.ollama/` — Cephyr quota) | [`tier1-basics/07-ollama-cluster-server`](../tier1-basics/07-ollama-cluster-server/) |
| 5 | **vLLM server** (self-hosted) | none | ✓ (GPU) | ✓ | ★ | Run in Docker or Apptainer; same recipe as cluster = clean parity | Canonical cluster open-weight server; launch via `vllm-server.sbatch`; clients talk over port-forward or node IP | [`tier2-combinations/11-multi-provider-inference`](../tier2-combinations/11-multi-provider-inference/) (`slurm/vllm-server.sbatch`) |
| 6a | **HF in-process — from C3SE shared hub** | `HF_TOKEN` only for gated | × | ✓ | ★ (zero-quota) | Shared hub path doesn't exist locally; N/A | Load from `/mimer/NOBACKUP/Datasets/LLM/huggingface/hub/` via `HF_HUB_OFFLINE=1` + snapshot path; use first for any model C3SE already mirrors | [`tier1-basics/03-hf-shared-hub`](../tier1-basics/03-hf-shared-hub/) |
| 6b | **HF in-process — clone + bundle into SIF / Docker image** | `HF_TOKEN` if gated | ✓ | ✓ (SIF only) | ★ | `huggingface-cli download` then bake into **SIF** (portable to cluster) **or** Docker image (local-only); one file = quota-safe | Run with the bundled SIF; `--bind` data & results at run time | [`tier1-basics/08-hf-sif-bundle`](../tier1-basics/08-hf-sif-bundle/) |
| 6c | **HF in-process — streaming from Hub** | `HF_TOKEN` if gated | ✓ | ⚠ | ⚠ | Plain `from_pretrained()`; cache → `HF_HOME` or `~/.cache/huggingface/`; fine for dev | Requires outbound internet from compute node + strict `HF_HOME=/mimer/…`; default `~/.cache/huggingface/` blows the 60k-file quota | [`tier1-basics/09-hf-hub-streaming`](../tier1-basics/09-hf-hub-streaming/) |
| 7 | **Git-cloned model repo → SIF or Docker image** | SSH / HTTPS git creds | ✓ | ✓ (SIF only) | ✓ | `git clone` the weights repo → build **SIF** (runs anywhere) or **Docker image** (laptop-only) | Two shapes: (a) bake weights into SIF at build time; (b) clone weights to Mimer and load by path. Never clone weights into `/cephyr/users/` | [`tier2-combinations/14-git-model-bundle`](../tier2-combinations/14-git-model-bundle/) |
| 8 | **Fine-tuning — LoRA / PEFT (adapter-level)** | `HF_TOKEN` if base gated | ✓ (small bases) | ✓ | ★ | Single laptop GPU for toy scale (≤ 3B base, short runs); inside Docker or Apptainer | Canonical cluster training pattern; outputs = small adapter files; bundle adapter + base into a SIF for downstream inference | [`tier1-basics/05-train-lora`](../tier1-basics/05-train-lora/) + [`tier2-combinations/13-train-infer-pipeline`](../tier2-combinations/13-train-infer-pipeline/) |
| 9 | **Fine-tuning — full / distributed (multi-GPU)** | `HF_TOKEN` if base gated | × | ✓ | ★ (cluster-only) | Full finetune of realistic models exceeds laptop VRAM/time | 4× A100 via DeepSpeed / FSDP / accelerate; sharded checkpoints → write to Mimer, not Cephyr | [`tier3-advanced/21-distributed-finetune`](../tier3-advanced/21-distributed-finetune/) |

## Quick read

- **Only ⚠ rows on cluster** are #1, #2, #6c — all "works but usually
  the wrong tool for a GPU allocation."
- **Preferred cluster patterns** (★): pre-downloaded HF hub (6a),
  SIF-bundled HF (6b), vLLM (5), LoRA (8), distributed finetune (9).
- **Zero-quota wins on cluster**: 5, 6a, 6b — 1 SIF file each,
  regardless of underlying model size.
- **Laptop-only realistic**: only #9 (full distributed finetune) is
  genuinely out of reach on a single laptop GPU.

## Decision table by task

| If you want to…                                           | Start from                                      |
|-----------------------------------------------------------|-------------------------------------------------|
| Call OpenAI / Anthropic / Gemini / Grok from code         | `tier1-basics/02-inference-api-token`           |
| Use a Claude / Gemini subscription inside scripted jobs   | `tier2-combinations/11-multi-provider-inference` |
| Host LM Studio on the cluster as an HTTP endpoint         | `tier1-basics/06-lmstudio-cluster-server`       |
| Host Ollama on the cluster as an HTTP endpoint            | `tier1-basics/07-ollama-cluster-server`         |
| Serve open-weight models with vLLM (fastest throughput)   | `tier2-combinations/11-multi-provider-inference` |
| Load a pre-downloaded HuggingFace model (zero-quota)      | `tier1-basics/03-hf-shared-hub`                 |
| Bake a HuggingFace model into a SIF once, reuse many jobs | `tier1-basics/08-hf-sif-bundle`                 |
| Stream a HuggingFace model from the Hub on demand         | `tier1-basics/09-hf-hub-streaming`              |
| Use a model distributed via git (not HF Hub)              | `tier2-combinations/14-git-model-bundle`        |
| Fine-tune a small base with LoRA                          | `tier1-basics/05-train-lora`                    |
| Wrap LoRA training + inference in a reproducible SIF      | `tier2-combinations/13-train-infer-pipeline`    |
| Full distributed finetune on 4× A100                      | `tier3-advanced/21-distributed-finetune`        |
| Surgically rearchitect + retrain an existing model        | `tier3-advanced/22-reconstruct-retrain-infer`   |
