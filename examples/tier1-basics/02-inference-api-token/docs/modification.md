# Modification — adapting `02-inference-api-token`

## Change provider (e.g., Azure OpenAI)

```ini
# .env
OPENAI_BASE_URL=https://my-azure-endpoint.openai.azure.com/openai/deployments/my-deployment
OPENAI_API_KEY=<azure-key>
OPENAI_MODEL=gpt-4o   # deployment name if Azure
```

No code changes — the SDK handles it.

## Point at a local vLLM / LM Studio / Ollama server

```ini
# .env (laptop dev, LM Studio running on host)
OPENAI_BASE_URL=http://host.docker.internal:1234/v1
OPENAI_API_KEY=lm-studio
OPENAI_MODEL=google/gemma-3-27b
```

This is how Tier 2's `11-multi-provider-inference` does it — under the
hood, all OpenAI-compatible endpoints are the same client call.

## Add a second provider

Don't. If you need more than one, use `11-multi-provider-inference`,
which adds Anthropic + Claude CLI + vLLM cleanly.

If you really insist on expanding in place:

1. Add `src/infer_api/providers/anthropic.py` with the same
   `predict(prompt, **kw) -> {text, raw, model, usage}` shape.
2. Register in `providers/__init__.py`.
3. Pass `--provider` in `scripts/infer.py`.

## Batch a dataset

Drop a CSV at `$DATA_DIR/prompts.csv`, then add a script:

```python
# scripts/infer_batch.py
import csv, json
from pathlib import Path
from infer_api import config, providers

rows = list(csv.DictReader(open(config.data_dir()/"prompts.csv")))
out  = []
for row in rows:
    r = providers.predict(row["prompt"])
    out.append({**row, "response": r["text"], "tokens": r["usage"]["total_tokens"]})
(config.ensure_results_dir() / "batch.json").write_text(json.dumps(out, indent=2))
```

Register in `pixi.toml`:
```toml
[tasks]
infer-batch = "python scripts/infer_batch.py"
```

## Add retry + rate limits

```toml
[pypi-dependencies]
tenacity = "*"
```

Then wrap `predict()`:
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(5), wait=wait_exponential(min=1, max=30))
def predict_with_retry(prompt, **kw):
    return predict(prompt, **kw)
```

## What NOT to change

Same rules as `01-foundation`: keep container paths, env-var names, and
pixi task names. The `predict()` return shape is a cross-template
contract — other templates expect `{text, raw, model, usage}`.
