# Modification — `07-ollama-cluster-server`

What to change when you copy this template into your own project.

## 1. Rename the Python package

Pick a `snake_case` package name (≤ 20 chars, no dots), e.g.
`crash_chat`. The package name must agree in **three** places or
imports break.

1. **Folder name** under `src/`:

   **PowerShell:**
   ```powershell
   Rename-Item src\ollama_cluster src\<your_pkg>
   ```
   **bash / zsh:**
   ```bash
   mv src/ollama_cluster src/<your_pkg>
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

- `slurm/ollama-server.sbatch`
- `slurm/infer-cpu.sbatch`

## 3. Swap the model

Ollama resolves model identifiers against **its own library** at
<https://ollama.com/library>. Identifiers look like
`<name>:<tag>` (tag picks quantization / parameter count), e.g.
`llama3.1:8b`, `qwen2.5:14b-instruct-q4_K_M`, `mistral:7b-instruct`.

Edit `.env`:

```ini
# original
OLLAMA_MODEL=llama3.1:8b

# examples
OLLAMA_MODEL=qwen2.5:14b
OLLAMA_MODEL=gemma2:27b-instruct-q5_K_M
OLLAMA_MODEL=llama3.1:70b-instruct-q4_K_M      # ~40 GiB
```

The sbatch runs `ollama pull $OLLAMA_MODEL` on startup — if the model
isn't cached in `$OLLAMA_MODELS` yet, it downloads the first time.
Budget the first request's wall clock accordingly (big models can
take 10–30 min on the compute node's egress).

No source change needed — the client passes whatever `OLLAMA_MODEL`
resolves to into the OpenAI `model=` field.

## 4. Change the port

Ollama's default is `11434`. If another job on the laptop (or a local
`ollama serve`) is already using it, pick a different port in `.env`:

```ini
OLLAMA_PORT=11535
```

The sbatch honours `$OLLAMA_PORT`, writes it to
`results/ollama-port.txt`, and the client reads from there. You can
also forward to a different *laptop-side* port without changing the
server:

```bash
ssh -L 9999:$HOST:$PORT alvis
OPENAI_BASE_URL=http://localhost:9999/v1 pixi run infer --prompt "hi"
```

## 5. Tune wall-clock and GPU size

`slurm/ollama-server.sbatch` defaults to 4 h on a single T4:

```
#SBATCH --time=0-04:00:00
#SBATCH --gpus-per-node=T4:1
```

Rules of thumb:

| Model size            | Recommended GPU            | Min `--mem` |
|-----------------------|----------------------------|-------------|
| up to 8 B, Q4_K_M     | `T4:1`                     | 32 G        |
| 13–14 B, Q4_K_M       | `A40:1`                    | 48 G        |
| 27–34 B, Q4/Q5        | `A100:1`                   | 80 G        |
| 70 B, Q4              | `A100fat:1` or `A100:2`    | 128 G       |

Raise `--time` for long sessions — the sbatch blocks on `ollama serve`
for the whole allocation.

## 6. Pre-pull the model on the login node

The default sbatch pulls lazily — the first `ollama pull` eats wall-clock
inside your allocation. Avoid this by pre-pulling once on a login node
(or interactive session):

**bash / zsh:**

```bash
mkdir -p "$OLLAMA_MODELS"
apptainer exec \
    --bind "$OLLAMA_MODELS":/tmp/ollama-models \
    --env  OLLAMA_MODELS=/tmp/ollama-models \
    ollama.sif \
    bash -c "ollama serve & SERVER=\$!; sleep 5; \
             ollama pull $OLLAMA_MODEL; kill \$SERVER"
```

Once the blob is in `$OLLAMA_MODELS`, every subsequent sbatch starts
instantly. Do this once per new model.

## What NOT to change

- Container paths (`/data`, `/results`, `/models`, `/workspace`) — other
  templates expect them.
- `OLLAMA_HOST=0.0.0.0:$PORT` in the sbatch — binding to localhost
  breaks port-forward.
- The `predict(prompt, **kw) -> {text, raw, model, usage}` shape in
  `src/<pkg>/client.py` — cross-template contract.
- Pixi task names (`smoke`, `info`, `infer`, `test`, `lint`).
