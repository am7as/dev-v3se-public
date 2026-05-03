# Usage — `11-multi-provider-inference` (step-by-step, zero to results)

A complete walkthrough from an empty folder to a working multi-provider
inference pipeline: one `pixi run infer` entrypoint driving **six**
distinct backends across four flavors — two cloud APIs (`openai`,
`gemini`), one CLI-subscription (`claude_cli`), two laptop / cluster
local servers (`lmstudio`, `ollama`), and a cluster-side vLLM A100
server (`vllm`). Picking the provider is a config knob
(`DEFAULT_PROVIDER` in `.env`, or `--provider X` at the CLI), not a
code change; the return shape (`{text, raw, model, usage}`) is
identical everywhere.

## 1. What you'll end up with

- Laptop dev loop where any of these works against the same code:
    - `pixi run infer --provider openai     --prompt "..."`
    - `pixi run infer --provider gemini     --prompt "..."`
    - `pixi run infer --provider claude_cli --prompt "..."`
    - `pixi run infer --provider lmstudio   --prompt "..."`  (LM Studio on host port 1234)
    - `pixi run infer --provider ollama     --prompt "..."`  (Ollama on host port 11434)
    - `pixi run infer --provider vllm       --prompt "..."`  (laptop test against any OpenAI-compatible URL)
- On Alvis: one `sbatch slurm/vllm-server.sbatch` that holds a GPU and
  writes `vllm-host.txt` + `vllm-port.txt` to `$RESULTS_DIR`, plus
  `sbatch slurm/infer-cpu.sbatch` that reads those files and calls the
  server from a cheap CPU node.
- Responses saved to `$RESULTS_DIR/responses/<provider>__<ts>.json`
  with `{provider, model, prompt, text, usage}`.

## 2. Prerequisites

**On laptop** (dev loop):

- Docker Desktop (Windows / macOS) or Docker Engine (Linux).
- `git`.
- For the `claude_cli` provider: `claude login` already done on the host
  (browser flow) so `~/.claude/` and `~/.claude.json` exist.
- Optional: Apptainer on WSL2 / Linux if you want to build SIFs locally.
  On macOS, skip and build on Alvis.

**On cluster**:

- C3SE account with Alvis allocation (NAISS project ID).
- SSH access to `alvis1.c3se.chalmers.se` / `alvis2.c3se.chalmers.se`.
- For `vllm`: an A100 slot (server sbatch requests `A100:1`).
- For `claude_cli` on the cluster: `~/.claude/` synced into Cephyr
  (personal, confidential — do **not** put it on a shared group path).

## 3. Clone the template

Pick a sibling folder for your new project.

**PowerShell (Windows):**

```powershell
Copy-Item . ..\my-infer-multi -Recurse
cd ..\my-infer-multi
```

**bash / zsh (macOS / Linux):**

```bash
cp -r . ../my-infer-multi
cd ../my-infer-multi
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

Edit `.env`. Each provider has its own labeled block; fill the ones
you'll actually use, leave the rest blank.

```ini
CEPHYR_USER=<cid>
CEPHYR_PROJECT_DIR=/cephyr/users/<cid>/Alvis/my-infer-multi
MIMER_GROUP_ROOT=/mimer/NOBACKUP/groups/<naiss-id>
MIMER_USER_DIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-infer-multi

# Default when --provider is omitted (one of: openai, gemini,
# claude_cli, lmstudio, ollama, vllm):
DEFAULT_PROVIDER=openai

# === Cloud APIs ===

# ---- openai ----
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
# OPENAI_BASE_URL=                # set only for Azure OpenAI

# ---- gemini ----
GEMINI_API_KEY=AIza...            # https://aistudio.google.com/apikey
GEMINI_MODEL=gemini-2.5-flash     # free-tier; gemini-flash-latest also works
# Gemini 2.5 charges hidden chain-of-thought tokens by default;
# set =0 to disable (cheapest), =-1 for unlimited (default), >0 to cap.
GEMINI_THINKING_BUDGET=

# === CLI subscription ===

# ---- claude_cli ----
CLAUDE_CLI_PATH=claude
CLAUDE_MODEL=claude-sonnet-4-6

# === Local servers (OpenAI-compatible HTTP) ===

# ---- lmstudio ----
LMSTUDIO_BASE_URL=http://host.docker.internal:1234/v1
LMSTUDIO_MODEL=google/gemma-4-e4b   # exact id from LM Studio's Loaded Models list

# ---- ollama ----
OLLAMA_BASE_URL=http://host.docker.internal:11434/v1
OLLAMA_MODEL=llama3.2:1b            # whatever you've `ollama pull`ed

# === Cluster server ===

# ---- vllm (host/port come from the server job at runtime) ----
VLLM_MODEL=google/gemma-2-9b-it
VLLM_HOST_FILE=/results/vllm-host.txt
VLLM_PORT_FILE=/results/vllm-port.txt
# For laptop tests against LM Studio/Ollama as a stand-in:
# VLLM_HOST=host.docker.internal
# VLLM_PORT=1234
```

Patch the Slurm `--account` line in **both** `slurm/*.sbatch` files:

```diff
-#SBATCH --account=<PROJECT_ID>
+#SBATCH --account=<naiss-id>
```

### CLI-subscription bind mount (laptop)

The `claude_cli` provider calls the real `claude` binary via subprocess
and needs your host credentials. Open `docker-compose.yml` and
uncomment the two volume lines:

```yaml
volumes:
  - .:/workspace
  # ...
  - ${CLAUDE_HOST_DIR}:/root/.claude
  - ${CLAUDE_HOST_JSON}:/root/.claude.json
```

Then add to `.env`:

```ini
# PowerShell-style path
CLAUDE_HOST_DIR=C:/Users/<you>/.claude
CLAUDE_HOST_JSON=C:/Users/<you>/.claude.json

# bash / zsh
# CLAUDE_HOST_DIR=/home/<you>/.claude
# CLAUDE_HOST_JSON=/home/<you>/.claude.json
```

## 5. Laptop smoke test (Docker + pixi)

```bash
docker compose up -d dev
docker compose exec dev pixi install
docker compose exec dev pixi run smoke
```

`smoke` prints a JSON per-provider status (`ok` / `missing X`). Expect
at least `openai: ok` if you set `OPENAI_API_KEY`. Then run one real
inference per reachable provider:

```bash
# Cloud APIs
docker compose exec dev pixi run infer --provider openai --prompt "hi"
docker compose exec dev pixi run infer --provider gemini --prompt "hi"

# CLI-subscription (needs ~/.claude bind-mount — see §4)
docker compose exec dev pixi run infer --provider claude_cli --prompt "hi"

# Local servers (start the server on host first, set <PROVIDER>_MODEL in .env)
docker compose exec dev pixi run infer --provider lmstudio --prompt "hi"
docker compose exec dev pixi run infer --provider ollama   --prompt "hi"

# vLLM (laptop): point VLLM_HOST/VLLM_PORT at any OpenAI-compatible server
docker compose exec dev pixi run infer --provider vllm     --prompt "hi"
```

Override the model per-call with `--model <id>` (otherwise the provider's
`*_MODEL` env var is used).

Each call appends to `results/responses/<provider>__<ts>.json`.

## 6. Build / bake step

Two Apptainer definitions ship with this example:

- `apptainer/dev.def` — interactive image; includes Node + `npm i -g
  @anthropic-ai/claude-code` so `claude_cli` works inside the container.
- `apptainer/app.def` — frozen inference image (bakes `src/`,
  `scripts/`, `configs/`); also includes the Claude CLI.

Neither is needed on the laptop if you use Docker Compose. They exist
for the cluster — build on Alvis in step 8.

## 7. Push to cluster (git preferred, rsync fallback)

### 7a. Git (recommended)

Create a **public** team remote, then:

```bash
git init -b main
git add .
git commit -m "initial scaffold"
git remote add origin git@github.com:<team>/<project>.git
git push -u origin main
```

On Alvis:

```bash
ssh <cid>@alvis2.c3se.chalmers.se
mkdir -p /cephyr/users/<cid>/Alvis
cd /cephyr/users/<cid>/Alvis
git clone git@github.com:<team>/<project>.git my-infer-multi
cd my-infer-multi
```

Copy `.env` separately (never committed):

**PowerShell:**

```powershell
scp .env <cid>@alvis2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/my-infer-multi/.env
```

**bash / zsh:**

```bash
scp .env <cid>@alvis2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/my-infer-multi/.env
```

### 7b. rsync fallback

**PowerShell:**

```powershell
bash _shared/scripts/sync-to-cephyr.sh
```

**bash / zsh:**

```bash
bash _shared/scripts/sync-to-cephyr.sh
```

The helper reads `CEPHYR_USER` / `CEPHYR_PROJECT_DIR` from `.env` and
excludes `.pixi/`, `results/`, `*.sif`, `.env`.

### 7c. Ship the Claude credentials (only if you want `claude_cli` on Alvis)

```bash
rsync -avh ~/.claude \
  <cid>@alvis2.c3se.chalmers.se:/cephyr/users/<cid>/.claude/
rsync -avh ~/.claude.json \
  <cid>@alvis2.c3se.chalmers.se:/cephyr/users/<cid>/.claude.json
```

These stay under your **personal** Cephyr root, never on a shared
group path.

## 8. Cluster setup

```bash
ssh <cid>@alvis2.c3se.chalmers.se
cd /cephyr/users/<cid>/Alvis/my-infer-multi

# Point Apptainer's cache at Mimer — Cephyr quota is tight.
export APPTAINER_CACHEDIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/apptainer-cache
mkdir -p "$APPTAINER_CACHEDIR"

# Dev SIF (interactive; used by the client job and for smokes).
apptainer build dev.sif apptainer/dev.def

# vLLM server SIF — only if you intend to use the vllm provider.
apptainer build vllm.sif ../../_shared/apptainer/vllm.def
```

First `dev.def` build: 3–6 min (pulls base + installs Node + Claude CLI).
`vllm.sif` is much larger; 8–15 min is typical.

## 9. Cluster smoke

```bash
# CPU smoke — imports every provider module, prints which are usable.
sbatch slurm/infer-cpu.sbatch
squeue -u $USER                              # wait for R, then CG
cat slurm-infer-multi-*.out
```

The infer-cpu job uses whatever `DEFAULT_PROVIDER` is in `.env`. For a
real GPU smoke of the `openai` / `claude_cli` providers (which only
need egress HTTPS), the CPU sbatch is enough. There is no `gpu-t4`
sbatch in this example; the only GPU workload here is the vLLM server
(step 10), which uses A100.

## 10. Run real workload

### openai / claude_cli (single-job)

Both providers work from a CPU node — they just call outbound HTTPS.

```bash
sbatch --export=ALL,PROVIDER=openai,PROMPT="Explain self-attention in one paragraph." \
       slurm/infer-cpu.sbatch
sbatch --export=ALL,PROVIDER=claude_cli,PROMPT="Give 3 bullet points on LoRA." \
       slurm/infer-cpu.sbatch
```

For `claude_cli`, uncomment the `CLAUDE_BINDS` line in
`slurm/infer-cpu.sbatch` so the SIF sees your credentials:

```bash
CLAUDE_BINDS="--bind /cephyr/users/$USER/.claude:/root/.claude \
              --bind /cephyr/users/$USER/.claude.json:/root/.claude.json"
```

### vllm — the two-job pattern

The vLLM provider is stateful: a long-running server job holds an A100,
and short client jobs talk to it via HTTP.

**Job 1 — launch the server:**

```bash
sbatch slurm/vllm-server.sbatch
# Wait until slurm-vllm-server-*.out says "Application startup complete".
# Meanwhile the job writes:
#     results/vllm-host.txt   ← compute-node hostname
#     results/vllm-port.txt   ← dynamically chosen free port
```

**Job 2 — launch the client(s):**

```bash
sbatch --export=ALL,PROVIDER=vllm,PROMPT="Summarize transformers in 2 lines." \
       slurm/infer-cpu.sbatch
```

The `vllm.py` provider reads the two files (under `$RESULTS_DIR/`
which is bound to `/results` inside the SIF) and opens an HTTP
connection to `http://<host>:<port>/v1`. Submit the client **after**
the server log prints "READY" — submitting earlier will fail with
"VLLM port not resolvable".

You can fire many client jobs against one server allocation — that's
the whole point of the split. Cancel the server with `scancel
<server-jobid>` when done to free the A100.

### Optional — peek at the server from laptop

If you want to hit the vLLM server interactively from your laptop:

**PowerShell:**

```powershell
$node = ssh <cid>@alvis2.c3se.chalmers.se "cat /cephyr/users/<cid>/Alvis/my-infer-multi/results/vllm-host.txt"
$port = ssh <cid>@alvis2.c3se.chalmers.se "cat /cephyr/users/<cid>/Alvis/my-infer-multi/results/vllm-port.txt"
ssh -N -L "${port}:${node}:${port}" <cid>@alvis2.c3se.chalmers.se
```

**bash / zsh:**

```bash
node=$(ssh <cid>@alvis2.c3se.chalmers.se "cat /cephyr/users/<cid>/Alvis/my-infer-multi/results/vllm-host.txt")
port=$(ssh <cid>@alvis2.c3se.chalmers.se "cat /cephyr/users/<cid>/Alvis/my-infer-multi/results/vllm-port.txt")
ssh -N -L "${port}:${node}:${port}" <cid>@alvis2.c3se.chalmers.se
```

Then with the tunnel open, point the laptop client at
`VLLM_HOST=localhost` and `VLLM_PORT=<port>`.

## 11. Retrieve results

**PowerShell:**

```powershell
rsync -avh --progress `
  <cid>@alvis2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/my-infer-multi/results/ `
  .\results\
```

**bash / zsh:**

```bash
rsync -avh --progress \
  <cid>@alvis2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/my-infer-multi/results/ \
  ./results/
```

Or use the helper:

```bash
bash _shared/scripts/sync-from-cephyr.sh          # results/ only
```

Open any `results/responses/*.json` — filenames are
`<provider>__<timestamp>.json`.

## 12. Verification checklist

- [ ] `.env` has real values for at least one of: `OPENAI_API_KEY`,
      `CLAUDE_HOST_DIR` + `CLAUDE_HOST_JSON`, `VLLM_MODEL`.
- [ ] `pixi run smoke` on laptop shows `status.ok` for the providers
      you configured.
- [ ] Both `slurm/*.sbatch` files have your real `--account=<naiss-id>`.
- [ ] `APPTAINER_CACHEDIR` points at Mimer (not Cephyr, not `$HOME`).
- [ ] `dev.sif` was built on Alvis and is present in the project root.
- [ ] For vLLM: `results/vllm-host.txt` and `results/vllm-port.txt`
      both exist **before** you submit the client job.
- [ ] `results/responses/*.json` contains entries with non-empty
      `text` and a matching `provider` name.

## 13. Troubleshooting

- **"OPENAI_API_KEY not set" from the CPU job** → you didn't ship `.env`
  to Cephyr, or the sbatch didn't source it. `slurm/infer-cpu.sbatch`
  sources `.env` only if present next to the submitted script.

- **`claude_cli` fails "`claude` binary not found"** → either the SIF
  didn't install the npm package (check build log for the npm line in
  `dev.def`), or the credential binds aren't active. Verify:
  `apptainer exec --bind /cephyr/users/$USER/.claude:/root/.claude
  dev.sif claude --version`.

- **`claude_cli` works in Docker but not on Alvis** → you forgot to
  rsync `~/.claude/` + `~/.claude.json` to Cephyr (step 7c), or the
  `CLAUDE_BINDS` line in `infer-cpu.sbatch` is still commented out.

- **vLLM client job errors "VLLM port not resolvable"** → the server
  isn't up yet. Tail its `.out` file until "Application startup
  complete" before submitting the client, or add a `sleep 60` /
  polling loop in front of the client call.

- **vLLM client runs but the generated text is empty** → the model
  field mismatches. vLLM requires the **same** model id the server
  was launched with. Check both jobs'
  `VLLM_MODEL` values match exactly.

- **Cephyr quota warning after building SIFs** → you didn't set
  `APPTAINER_CACHEDIR` before `apptainer build`. Move the cache:
  `mv ~/.apptainer $APPTAINER_CACHEDIR && ln -s $APPTAINER_CACHEDIR
  ~/.apptainer`.
