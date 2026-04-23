# `11-multi-provider-inference` — switch LLM provider by config

Composes `02-inference-api-token` with two more provider flavors:

1. **API token** (OpenAI-compatible — OpenAI, Azure, vLLM, LM Studio, Ollama)
2. **CLI subscription** (Claude Code CLI, Gemini CLI — uses your
   Pro/Max subscription via subprocess)
3. **vLLM server** (Alvis-sanctioned open-weight serving — launched via
   `slurm/vllm-server.sbatch`, client connects to its port)

One `pixi run infer` entrypoint. Pick which provider via `.env` or
`--provider`. Same `{text, raw, model, usage}` return shape everywhere.

## What's new vs Tier 1

- `src/infer_multi/providers/` — three modules: `openai_api.py`,
  `claude_cli.py`, `vllm.py`. Each exposes `NAME` + `predict()`.
- `src/infer_multi/router.py` — picks the provider by name.
- `configs/providers.yaml` — the provider registry.
- `scripts/infer.py` — `--provider openai|claude_cli|vllm`.
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

# OpenAI
docker compose exec dev pixi run infer --provider openai --prompt "hi"

# Claude CLI (requires `claude login` on host + bind ~/.claude)
docker compose exec dev pixi run infer --provider claude_cli --prompt "hi"

# vLLM (laptop — point at LM Studio/Ollama for local testing)
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
