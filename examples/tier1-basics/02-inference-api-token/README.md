# `02-inference-api-token` — one LLM via API token

Extends `01-foundation` with exactly one thing: calling a commercial LLM
API from token credentials. OpenAI GPT-4o is the default; swap via
`.env`.

## What's new vs foundation

- `src/infer_api/providers/openai.py` — a single provider module.
- `scripts/infer.py` — `pixi run infer --prompt "hello"` calls the API
  and writes the response to `$RESULTS_DIR/responses/<ts>.json`.
- `.env.example` gets `OPENAI_API_KEY`, `OPENAI_MODEL`.

## What's **not** here (by design)

- Multi-provider routing → see `11-multi-provider-inference`.
- CLI-subscription auth → see `11-multi-provider-inference`.
- Open-weight models → see `03-hf-shared-hub` or `11`.
- Complex prompt templates / datasets → bring your own.

## Quickstart

```powershell
Copy-Item . ..\my-project -Recurse
cd ..\my-project
Copy-Item .env.example .env
# Put your OPENAI_API_KEY in .env
docker compose up -d dev
docker compose exec dev pixi install
docker compose exec dev pixi run smoke
docker compose exec dev pixi run infer --prompt "What's 2+2?"
cat ..\results\responses\*.json
```

## On Alvis

Same as foundation. Compute nodes have outbound HTTPS — the API call
works inside sbatch without extra config. See
`slurm/infer-cpu.sbatch` (no GPU needed for API calls).

## Docs

- [docs/usage.md](docs/usage.md) — the `pixi run infer` flow
- [docs/modification.md](docs/modification.md) — adding more providers,
  prompts, batch runs
- Foundation docs still apply for structure/setup/troubleshooting:
  [`../01-foundation/docs/`](../01-foundation/docs/).
