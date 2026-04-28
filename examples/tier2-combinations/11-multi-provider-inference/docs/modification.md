# Modification — `11-multi-provider-inference`

## Add a seventh provider

The shipped registry has six (`openai`, `gemini`, `claude_cli`,
`lmstudio`, `ollama`, `vllm`). Adding another follows the same five
steps. Example for Anthropic's API directly:

1. `src/infer_multi/providers/anthropic.py`:
   ```python
   from anthropic import Anthropic
   NAME = "anthropic"
   def predict(prompt, *, model=None, **kw):
       c = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
       m = model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
       resp = c.messages.create(model=m, max_tokens=1024,
                                 messages=[{"role":"user","content":prompt}])
       return {"text": resp.content[0].text, "raw": resp.model_dump(),
               "model": m, "usage": {"prompt_tokens": resp.usage.input_tokens, ...}}
   ```
2. Add to `providers/__init__.py`:
   ```python
   from . import anthropic
   _PROVIDERS[anthropic.NAME] = anthropic
   ```
3. Add `anthropic = "*"` to `pixi.toml [pypi-dependencies]`.
4. Add `ANTHROPIC_API_KEY` to `.env.example`.
5. Register in `configs/providers.yaml`.

## Make a provider streaming

Add a `predict_stream(prompt, ...) -> Iterator[str]` alongside `predict()`.
Most OpenAI-compatible providers support `stream=True`; Claude CLI
streams naturally via stdout.

## Batch across providers

See `docs/usage.md` → "Batch: one prompt, all providers". For hundreds
of prompts, write a script that iterates a dataset and calls
`router.predict()` in a thread pool (APIs) or sequentially (CLI).

## Cap cost per run

```python
from infer_multi import router
total = 0
for prompt in prompts:
    r = router.predict(prompt)
    total += r["usage"]["total_tokens"]
    if total > 100_000:
        print("Token budget exhausted")
        break
```

## What NOT to change

- `predict()` return shape `{text, raw, model, usage}`. All six shipped
  providers match it.
- Env-var names declared in each `providers/*.py` (e.g. `OPENAI_API_KEY`,
  `GEMINI_THINKING_BUDGET`, `LMSTUDIO_BASE_URL`).
- Container paths (`/data`, `/results`, `/models`).
