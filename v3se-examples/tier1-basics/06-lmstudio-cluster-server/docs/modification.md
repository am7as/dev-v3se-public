# Modification — `06-lmstudio-cluster-server`

What to change when you copy this template into your own project.

## 1. Rename the Python package

Pick a `snake_case` package name (≤ 20 chars, no dots), e.g.
`traffic_chat`. The package name appears in **three** places; all three
must agree or imports break.

1. **Folder name** under `src/`:

   **PowerShell:**
   ```powershell
   Rename-Item src\lmstudio_cluster src\<your_pkg>
   ```
   **bash / zsh:**
   ```bash
   mv src/lmstudio_cluster src/<your_pkg>
   ```

2. **`pyproject.toml`** (two fields):
   ```toml
   [project]
   name = "<your-pkg>"

   [tool.hatch.build.targets.wheel]
   packages = ["src/<your_pkg>"]
   ```

3. **`pixi.toml`** (two fields):
   ```toml
   [workspace]
   name = "<your-pkg>"

   [pypi-dependencies]
   <your_pkg> = { path = ".", editable = true }
   ```

Re-install editable after renaming:

```bash
docker compose exec dev pixi install
```

## 2. Set the Slurm account

Every `slurm/*.sbatch` starts with `#SBATCH --account=<PROJECT_ID>`.
Replace the placeholder with your real NAISS id in each file:

```diff
-#SBATCH --account=<PROJECT_ID>
+#SBATCH --account=NAISS2024-5-123
```

Files to edit:

- `slurm/lmstudio-server.sbatch`
- `slurm/infer-cpu.sbatch`

Alternatively, `ALVIS_ACCOUNT=<naiss-id>` in `.env` and add
`#SBATCH --account=$ALVIS_ACCOUNT` — but expanding `$VAR` inside
`#SBATCH` directives is fiddly; editing literally is safer.

## 3. Swap the model

LM Studio resolves model identifiers against **its own catalog** at
<https://lmstudio.ai/models>. Identifiers look like
`<org>/<model-name>` and map to GGUF files served by LM Studio's
community mirror.

Edit `.env`:

```ini
# original
LMSTUDIO_MODEL=lmstudio-community/llama-3.1-8b-instruct

# examples
LMSTUDIO_MODEL=lmstudio-community/qwen2.5-7b-instruct
LMSTUDIO_MODEL=lmstudio-community/gemma-2-9b-it
LMSTUDIO_MODEL=bartowski/Meta-Llama-3.1-70B-Instruct-GGUF   # 40+ GiB
```

The first time a new model is requested, `lms server` pulls the GGUF
into `$LMSTUDIO_CACHE_DIR` (Mimer). Budget the first request's wall
clock accordingly (big models can take 10–30 min to download).

No source change needed — the client passes whatever `LMSTUDIO_MODEL`
resolves to into the OpenAI `model=` field.

## 4. Tune wall-clock and GPU size

`slurm/lmstudio-server.sbatch` defaults to 4 h on a single T4:

```
#SBATCH --time=0-04:00:00
#SBATCH --gpus-per-node=T4:1
```

Rules of thumb:

| Model size           | Recommended GPU            | Min `--mem` |
|----------------------|----------------------------|-------------|
| up to 8 B, Q4/Q5     | `T4:1`                     | 32 G        |
| 13–14 B, Q4/Q5       | `A40:1`                    | 48 G        |
| 30–34 B, Q4/Q5       | `A100:1`                   | 80 G        |
| 70 B, Q4             | `A100fat:1` or `A100:2`    | 128 G       |

Raise `--time` for long-running evaluation sessions. Note the sbatch
writes `lmstudio-{host,port}.txt` then blocks for the full wall-clock,
so pick a value close to your actual session length.

## 5. Change the forwarded port

The sbatch picks a random TCP port in the 20000–40000 range and writes
it to `$RESULTS_DIR/lmstudio-port.txt`. The laptop port in
`ssh -L <laptop>:<node>:<remote>` can be anything free on the laptop;
if it collides pick something else:

```bash
ssh -L 9999:$HOST:$PORT alvis
OPENAI_BASE_URL=http://localhost:9999/v1 pixi run infer --prompt "hi"
```

No code changes needed — `client.py` reads whatever `OPENAI_BASE_URL`
resolves to.

## 6. Pre-warm the model cache (optional)

LM Studio won't fetch the model until the first completion request
actually arrives, and its download runs inside the Slurm allocation
(eating your wall-clock). To pre-populate on a login node instead:

```bash
apptainer exec \
    --bind "$LMSTUDIO_CACHE_DIR":/tmp/lmstudio \
    --env LMSTUDIO_CACHE_DIR=/tmp/lmstudio \
    lmstudio.sif \
    lms get "$LMSTUDIO_MODEL"
```

Subsequent sbatch runs reuse the cached weights.

## What NOT to change

- Container paths (`/data`, `/results`, `/models`, `/workspace`) — other
  templates expect them.
- The `predict(prompt, **kw) -> {text, raw, model, usage}` shape in
  `src/<pkg>/client.py` — cross-template contract.
- Pixi task names (`smoke`, `info`, `infer`, `test`, `lint`).
- Host bind on `0.0.0.0` in the sbatch — SSH port-forward needs it.
