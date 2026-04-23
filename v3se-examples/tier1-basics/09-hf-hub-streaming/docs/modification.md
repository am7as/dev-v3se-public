# Modification — `09-hf-hub-streaming`

Everything you might realistically need to change when you adapt this
template to a real project. `usage.md` covers the *first* walkthrough;
this file is the follow-up edit list.

## 1. Rename the Python package

The package is shipped as `hf_hub_streaming`. Rename in three places,
then reinstall:

1. Folder: `src/hf_hub_streaming/` → `src/<your_pkg>/`.
2. `pyproject.toml`:

   ```toml
   [tool.hatch.build.targets.wheel]
   packages = ["src/<your_pkg>"]
   ```
3. `pixi.toml` — the `[workspace]` name and any references in
   `[tasks]` if you hard-coded the package elsewhere.
4. Import sites: `scripts/infer.py`, `scripts/info.py`,
   `scripts/smoke.py`, `tests/test_smoke.py` all do
   `from hf_hub_streaming import ...`.

Then:

**PowerShell:**

```powershell
docker compose exec dev pixi install --force
```

**bash / zsh:**

```bash
docker compose exec dev pixi install --force
```

## 2. Set the Slurm account

Every `slurm/*.sbatch` ships with a placeholder:

```diff
-#SBATCH --account=<PROJECT_ID>
+#SBATCH --account=<your-naiss-id>
```

Do this in every file under `slurm/` — right now that is
`slurm/gpu-t4.sbatch`, but any extra sbatch you add needs the same
edit.

## 3. Swap the model

Single-line change in `.env`:

```ini
HF_MODEL=meta-llama/Llama-3.2-3B-Instruct
HF_TOKEN=hf_xxx          # required for gated repos
```

No code change needed — `src/hf_hub_streaming/model.py` forwards
`HF_MODEL` directly to `AutoTokenizer.from_pretrained()` /
`AutoModelForCausalLM.from_pretrained()`. For non-CausalLM
architectures (e.g. vision-language), swap the classes in `model.py`
to match the model card (`AutoModelForImageTextToText`,
`AutoModelForSpeechSeq2Seq`, ...).

## 4. Point `HF_HOME` at Mimer (mandatory on Alvis)

Laptop `.env`:

```ini
HF_HOME=/workspace/.hf-cache
TRANSFORMERS_CACHE=/workspace/.hf-cache
```

Cluster `.env` — **must** differ:

```ini
HF_HOME=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/<project>/.hf-cache
TRANSFORMERS_CACHE=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/<project>/.hf-cache
```

The sbatch already re-exports `HF_HOME` with a fallback of
`$PWD/.hf-cache`. Since `$PWD` is under Cephyr, the `.env` value is
what saves you — double-check that line survives edits. The loader in
`model.py` prints a warning if `HF_HOME` starts with `$HOME` or
`/cephyr/`.

## 5. Gated models — HF token

For Llama, gemma-*-it, Mistral Instruct variants etc., accept the
licence on the model card **in a browser** first, then:

```ini
# .env
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxx
```

Verify before sbatch:

```bash
set -a; . ./.env; set +a
curl -sH "Authorization: Bearer $HF_TOKEN" \
  https://huggingface.co/api/models/$HF_MODEL | head -c 200
```

A JSON with `"modelId"` = OK. `401` = token wrong or licence not
accepted.

## 6. Wall-clock and GPU size

Defaults in `slurm/gpu-t4.sbatch` target a single T4 for 30 minutes.
Adapt per model:

| Model size | Suggested GPU | Wall-clock |
|------------|---------------|------------|
| ≤ 3 B params | `T4:1` | 30 min |
| 7–13 B | `A40:1` | 1 h |
| 30 B+ | `A100:2` or `A100fat:1` | 2 h |

```diff
-#SBATCH --time=0-00:30:00
-#SBATCH --gpus-per-node=T4:1
-#SBATCH --mem=32G
+#SBATCH --time=0-02:00:00
+#SBATCH --gpus-per-node=A100:2
+#SBATCH --mem=120G
```

Bigger models also need `HF_DTYPE=bfloat16` (default `auto` usually
picks right, but pin it for reproducibility).

## 7. Quantized inference (save GPU memory)

Add a dependency:

```toml
# pixi.toml
[pypi-dependencies]
bitsandbytes = "*"
```

Then in `src/hf_hub_streaming/model.py`, inside `load()`:

```python
from transformers import BitsAndBytesConfig
bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16)
model = AutoModelForCausalLM.from_pretrained(source, quantization_config=bnb, ...)
```

~4x memory savings, minor quality loss. Required for running 30B+
models on a single A40.

## 8. Bigger prompts / output

```ini
HF_MAX_NEW_TOKENS=1024
```

For input-side limits (long docs), set
`model.config.max_position_embeddings` awareness into `generate()`
yourself — the template doesn't chunk.

## 9. What NOT to change

- `generate()` return shape `{text, model, device, usage}`. Downstream
  examples (11-multi-provider-inference, 13-train-infer-pipeline)
  compose this. Add keys; don't remove them.
- Env-var names `HF_MODEL`, `HF_HOME`, `HF_TOKEN`, `HF_DEVICE`,
  `HF_DTYPE`, `HF_MAX_NEW_TOKENS`. These match 03 and 08 so swapping
  backends is a one-line change.
- The `_check_hf_home()` guard in `model.py`. It is the only thing
  between a typo in `.env` and a full Cephyr quota.
