# `11-multi-provider-inference` — switch LLM provider by config

One `pixi run infer` entrypoint, six providers split across four
flavours. Pick one via `.env` (`DEFAULT_PROVIDER=`) or at the CLI
(`--provider X`). Same `{text, raw, model, usage}` return shape
everywhere.

| Flavour            | Provider     | Notes                                                      |
|--------------------|--------------|------------------------------------------------------------|
| Cloud API          | `openai`     | OpenAI / Azure (set `OPENAI_BASE_URL` for Azure)           |
| Cloud API          | `gemini`     | Google `google-genai` SDK; free-tier `gemini-2.5-flash`    |
| CLI subscription   | `claude_cli` | Drives the local `claude` binary, uses your Pro/Max sub    |
| Local server       | `lmstudio`   | LM Studio's HTTP endpoint (laptop or Alvis via 06)         |
| Local server       | `ollama`     | Ollama's OpenAI-compatible endpoint (laptop or Alvis via 07) |
| Cluster server     | `vllm`       | Alvis A100 server; sbatch handshake via host/port files    |

## What's new vs Tier 1

- `src/infer_multi/providers/` — six modules, each exposes `NAME` +
  `predict()`: `openai_api.py`, `gemini.py`, `claude_cli.py`,
  `lmstudio.py`, `ollama.py`, `vllm.py`.
- `src/infer_multi/router.py` — picks the provider by name.
- `configs/providers.yaml` — the provider registry.
- `scripts/infer.py` — `--provider openai|gemini|claude_cli|lmstudio|ollama|vllm`.
- `slurm/vllm-server.sbatch` — launches the vLLM server; writes
  `vllm-port.txt` + `vllm-host.txt` under `$RESULTS_DIR` so the client
  job can connect.

## Quickstart

```powershell
Copy-Item . ..\my-project -Recurse
cd ..\my-project
Copy-Item .env.example .env
docker compose up -d dev
docker compose exec dev pixi install

# OpenAI cloud (set OPENAI_API_KEY in .env)
docker compose exec dev pixi run infer --provider openai --prompt "hi"

# Gemini cloud (set GEMINI_API_KEY in .env; free-tier gemini-2.5-flash)
docker compose exec dev pixi run infer --provider gemini --prompt "hi"

# Claude CLI (requires `claude login` on host + bind ~/.claude)
docker compose exec dev pixi run infer --provider claude_cli --prompt "hi"

# LM Studio local (start the LM Studio server on host with a model loaded;
# set LMSTUDIO_MODEL to the loaded model id)
docker compose exec dev pixi run infer --provider lmstudio --prompt "hi"

# Ollama local (run `ollama serve` on host + `ollama pull <model>`;
# set OLLAMA_MODEL to that model name)
docker compose exec dev pixi run infer --provider ollama --prompt "hi"

# vLLM cluster (laptop test: point VLLM_HOST/PORT at any OpenAI-compatible server)
docker compose exec dev pixi run infer --provider vllm --prompt "hi"
```

## On Alvis

**Token and CLI** work via compute-node outbound HTTPS.

**vLLM** requires the two-job pattern:

```bash
# Terminal 1: launch the server
sbatch slurm/vllm-server.sbatch
# Wait for "Application startup complete" in slurm-vllm-server-*.out

# Terminal 2: run the client
sbatch slurm/infer-cpu.sbatch   # reads vllm-port.txt / vllm-host.txt
```

See [docs/usage.md](docs/usage.md) for the full pattern.

## When to leave

- Just one provider, simpler → back to `02-inference-api-token` or `03-hf-shared-hub`.
- Want to swap data source too → `12-multi-source-data`.
- Adding finetuning → `13-train-infer-pipeline`.
