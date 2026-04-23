# Usage — `02-inference-api-token` (step-by-step, zero to results)

A complete walkthrough from an empty folder to your first OpenAI-API
response file, both on your laptop and inside an Alvis CPU sbatch job.
API calls are network-bound, not compute-bound — no GPU needed on the
cluster side.

## 1. What you'll end up with

- `pixi run infer --prompt "..."` prints a completion locally and
  writes a JSON record to `$RESULTS_DIR/responses/<timestamp>.json`.
- The same job runs inside `slurm/infer-cpu.sbatch` on Alvis, using
  your `OPENAI_API_KEY` from `.env` and the cluster's outbound HTTPS.
- A reproducible response log: prompt + model + text + token usage per
  run.

## 2. Prerequisites

**On laptop** (dev loop):

- Docker Desktop (Windows / macOS) or Docker Engine (Linux).
- `git` and an OpenAI API key (or a compatible base URL + key for
  Azure, vLLM-OpenAI, OpenRouter, etc.).

**On cluster**:

- C3SE account with an Alvis allocation (`<PROJECT_ID>` = your NAISS
  project ID).
- SSH to `alvis2.c3se.chalmers.se`. Compute nodes have outbound HTTPS,
  so API calls work without proxy/VPN.
- Cephyr home `/cephyr/users/<cid>/Alvis/` and Mimer group directory
  `/mimer/NOBACKUP/groups/<naiss-id>/`.

## 3. Clone the template

**PowerShell (Windows):**

```powershell
Copy-Item . ..\my-infer-api -Recurse
cd ..\my-infer-api
```

**bash / zsh (macOS / Linux):**

```bash
cp -r . ../my-infer-api
cd ../my-infer-api
```

## 4. Configure `.env`

**PowerShell:**

```powershell
Copy-Item .env.example .env
```

**bash / zsh:**

```bash
cp .env.example .env
```

Edit `.env`:

```ini
# Container paths — leave as-is.
DATA_DIR=/data
RESULTS_DIR=/results
MODELS_DIR=/models
WORKSPACE_DIR=/workspace
LOG_LEVEL=INFO

# Host bind mounts — blank = sibling defaults.
DATA_HOST=
RESULTS_HOST=
MODELS_HOST=

# Cephyr (code) + Alvis login.
CEPHYR_USER=<cid>
CEPHYR_PROJECT_PATH=/cephyr/users/<cid>/Alvis/my-infer-api
CEPHYR_TRANSFER_HOST=vera2.c3se.chalmers.se
ALVIS_LOGIN_HOST=alvis2.c3se.chalmers.se
ALVIS_ACCOUNT=<naiss-id>
MIMER_GROUP_PATH=/mimer/NOBACKUP/groups/<naiss-id>
MIMER_PROJECT_PATH=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-infer-api

# --- OPENAI (the provider this template uses) ---
OPENAI_API_KEY=sk-...your-key-here...
OPENAI_MODEL=gpt-4o-mini
# Leave empty for openai.com; set for Azure / vLLM-OpenAI / OpenRouter.
OPENAI_BASE_URL=

JUPYTER_PORT=7888
```

Replace `<PROJECT_ID>` in `slurm/infer-cpu.sbatch`:

```diff
-#SBATCH --account=<PROJECT_ID>
+#SBATCH --account=<naiss-id>
```

> `.env` holds a real secret. It is already in `.gitignore`. Never
> commit it. Never paste it into a cluster shell where `HISTFILE`
> captures history — use `scp`.

## 5. Laptop smoke test

Bring up the dev container, install Pixi deps, run the smoke plumbing
check (no API call yet), then actually call the API.

**PowerShell:**

```powershell
docker compose up -d dev
docker compose exec dev pixi install
docker compose exec dev pixi run smoke
docker compose exec dev pixi run infer --prompt "What is 2+2? Answer in one word."
Get-Content ..\results\responses\*.json | Select-Object -Last 30
```

**bash / zsh:**

```bash
docker compose up -d dev
docker compose exec dev pixi install
docker compose exec dev pixi run smoke
docker compose exec dev pixi run infer --prompt "What is 2+2? Answer in one word."
cat ../results/responses/*.json
```

Expected: stdout shows `Four` (or similar), followed by a line with the
output JSON path. The JSON has `prompt`, `model`, `text`, and `usage`
(prompt_tokens / completion_tokens / total_tokens).

Prompt from a file is equivalent:

**PowerShell:**

```powershell
Set-Content prompt.txt "Summarize quantum entanglement in two sentences."
docker compose exec dev pixi run infer --prompt-file prompt.txt
```

**bash / zsh:**

```bash
echo "Summarize quantum entanglement in two sentences." > prompt.txt
docker compose exec dev pixi run infer --prompt-file prompt.txt
```

## 6. Build step (not applicable)

No image bake needed for dev mode — this template uses the standard
bind-mounted dev SIF from `apptainer/dev.def`. You can skip straight
to the Alvis-side build in section 8.

## 7. Push to cluster

### Git (preferred)

```bash
git init -b main
git add .env.example .gitignore pixi.toml pyproject.toml README.md \
        apptainer/ configs/ docker-compose.yml docs/ scripts/ slurm/ \
        src/ tests/
git commit -m "initial infer-api scaffold"
git remote add origin git@github.com:<team>/my-infer-api.git
git push -u origin main
```

On the cluster:

```bash
ssh <cid>@alvis2.c3se.chalmers.se
mkdir -p /cephyr/users/<cid>/Alvis
cd /cephyr/users/<cid>/Alvis
git clone git@github.com:<team>/my-infer-api.git
cd my-infer-api
```

Copy the `.env` (contains the secret) from laptop to cluster — never
commit it.

**PowerShell:**

```powershell
scp .env <cid>@vera2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/my-infer-api/.env
```

**bash / zsh:**

```bash
scp .env <cid>@vera2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/my-infer-api/.env
```

### rsync (fallback — solo workflow)

```bash
bash ../../_shared/scripts/sync-to-cephyr.sh
```

## 8. Cluster setup

SSH in, point the Apptainer cache at Mimer (NOT Cephyr — respect the
30 GiB / 60k-file Cephyr quota), then build the dev SIF.

```bash
ssh <cid>@alvis2.c3se.chalmers.se
cd /cephyr/users/<cid>/Alvis/my-infer-api

export APPTAINER_CACHEDIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/apptainer-cache
mkdir -p "$APPTAINER_CACHEDIR"

apptainer build dev.sif apptainer/dev.def
```

First build: 2-5 minutes.

## 9. Cluster smoke

Trigger a real API call from an sbatch. The job sources `.env`, so the
API key is present even though it's never logged.

```bash
sbatch --export=ALL,PROMPT="What is the capital of France?" slurm/infer-cpu.sbatch
squeue -u $USER
cat slurm-infer-api-*.out
```

Expected output in the `.out` file:

- A one-line completion (e.g. "Paris.").
- The path of the new `results/responses/<ts>.json`.

If you leave `--export=ALL,PROMPT=...` off, the sbatch uses its
built-in default ("What is the capital of France?"). Good for a
minimal green-smoke check.

## 10. Run the real workload

Iterate a CSV of prompts from the cluster. Add a script alongside
`scripts/infer.py`, e.g. `scripts/infer_batch.py`:

```python
import csv, json, sys
from infer_api.providers import predict
from infer_api import config

src = sys.argv[1]            # /data/prompts.csv
out_dir = config.ensure_results_dir() / "responses"
out_dir.mkdir(parents=True, exist_ok=True)

with open(src) as f:
    for row in csv.DictReader(f):
        r = predict(row["prompt"])
        print(row["id"], "->", r["text"][:60])
```

Add a pixi task:

```toml
[tasks]
infer-batch = "python scripts/infer_batch.py"
```

Then bind a prompts directory on Mimer and run:

```bash
sbatch --export=ALL slurm/infer-cpu.sbatch
# edit the sbatch's apptainer run line to:
#   apptainer run \
#     --bind .:/workspace \
#     --bind /mimer/NOBACKUP/groups/<naiss-id>/<cid>/prompts:/data \
#     "$SIF" pixi run infer-batch /data/prompts.csv
```

For a small batch, running from the Alvis login node via
`apptainer run --bind .:/workspace dev.sif pixi run infer --prompt "..."`
also works — but only for interactive checks, not long jobs.

## 11. Retrieve results

From the laptop, pull responses back.

**PowerShell:**

```powershell
rsync -avh --progress `
  <cid>@vera2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/my-infer-api/results/ `
  .\results\
```

**bash / zsh:**

```bash
rsync -avh --progress \
  <cid>@vera2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/my-infer-api/results/ \
  ./results/
```

Or:

```bash
bash ../../_shared/scripts/sync-from-cephyr.sh
```

Inspect a response:

**PowerShell:**

```powershell
Get-Content .\results\responses\*.json | Select-String '"text"'
```

**bash / zsh:**

```bash
jq '.text, .usage' results/responses/*.json
```

## 12. Verification checklist

- [ ] `.env` filled in, `OPENAI_API_KEY` starts with `sk-` and is NOT
      tracked by git (check `git status`).
- [ ] `slurm/infer-cpu.sbatch` has a real `--account=<naiss-id>`.
- [ ] Local `pixi run infer --prompt "..."` printed a completion and
      wrote `../results/responses/*.json`.
- [ ] `.env` copied to Cephyr via `scp` (NOT committed).
- [ ] `dev.sif` built on Alvis with `APPTAINER_CACHEDIR` on Mimer.
- [ ] `sbatch slurm/infer-cpu.sbatch` reached `CD` state in under a
      minute; `.out` contains a completion.
- [ ] `results/responses/*.json` on cluster has non-empty `text` and
      non-zero `usage.total_tokens`.
- [ ] Results rsynced back to laptop.

## 13. Troubleshooting

- **`openai.AuthenticationError: Incorrect API key provided`** →
  `.env` on this side doesn't have the key, OR the sbatch didn't
  source it. Check `[ -f .env ] && ...` is present in the sbatch and
  that the key value isn't quoted weirdly.
- **`openai.APIConnectionError` inside an Alvis job** → a specific
  compute node lost outbound HTTPS. Rare but happens. Resubmit; use
  `--constraint=...` to target a different node class if it persists.
- **Completion shows as `null` in the JSON** → the API refused for
  content-policy reasons or your `OPENAI_MODEL` doesn't support the
  requested operation. Try `OPENAI_MODEL=gpt-4o-mini` as a baseline.
- **Cost surprise** → `usage.total_tokens` is logged for every call.
  Grep your JSONs: `jq '.usage.total_tokens' results/responses/*.json`
  and sum. Set a low per-run budget with a deliberately small
  `--prompt`.
- **Azure / vLLM-OpenAI / OpenRouter don't work** → set
  `OPENAI_BASE_URL` in `.env` (e.g.
  `https://<name>.openai.azure.com/openai/deployments/<deployment>`)
  and match the API key format that backend expects.
- **Need a second provider (Anthropic, Cohere, ...)** → leave this
  template. `11-multi-provider-inference` adds the routing layer
  without ABC/base-class boilerplate.
