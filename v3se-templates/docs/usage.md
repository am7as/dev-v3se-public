# Usage — `v3se-templates` (step-by-step, zero to results)

A complete walkthrough from an empty folder to a green run manifest in
all three V3SE execution modes: Docker on your laptop, Apptainer on
your laptop, and Apptainer inside an sbatch job on Alvis.

This scaffold is **tokenised** — three literal placeholders
(`__PACKAGE_NAME__`, `__PROJECT_SLUG__`, `__PROJECT_DESCRIPTION__`)
live in `pixi.toml`, `pyproject.toml`, `.env.example`, and the
`src/__PACKAGE_NAME__/` directory. Nothing installs until you run the
one-shot instantiate script (section 3). After that you have a normal
Python project and the rest of the walkthrough matches any tier
example.

## 1. Prerequisites

**On laptop** (dev loop):

- Docker Desktop (Windows / macOS) or Docker Engine (Linux).
- `git` (any recent version).
- PowerShell 7+ on Windows, or bash / zsh on macOS / Linux.
- Optional: Apptainer on WSL2 / Linux if you want to reproduce the SIF
  run locally. On macOS, skip local Apptainer and build on Alvis.

**On cluster**:

- C3SE account with an Alvis allocation. `<PROJECT_ID>` = your NAISS
  project ID, typically `NAISS2024-22-xxxx`.
- Cephyr home under `/cephyr/users/<cid>/Alvis/` and a Mimer group
  directory under `/mimer/NOBACKUP/groups/<naiss-id>/`.
- SSH access to `alvis1.c3se.chalmers.se` or `alvis2.c3se.chalmers.se`.

## 2. Clone / copy the template

Pick a sibling folder for your new project. The template directory
itself is never instantiated in place — always copy first.

**PowerShell (Windows):**

```powershell
Copy-Item . ..\<project> -Recurse
cd ..\<project>
```

**bash / zsh (macOS / Linux):**

```bash
cp -r . ../<project>
cd ../<project>
```

Replace `<project>` with the directory name you want (kebab-case is
conventional, e.g. `crash-survey`).

## 3. Instantiate — substitute tokens into real names

The scaffold does not work until the three placeholder tokens are
replaced. Run the shipped bootstrapper; it is interactive by default
and validates your inputs.

**PowerShell:**

```powershell
.\scripts\instantiate.ps1
```

**bash / zsh:**

```bash
bash scripts/instantiate.sh
```

The script prompts for:

| Token                         | Format                                  | Example            |
|-------------------------------|-----------------------------------------|--------------------|
| `__PACKAGE_NAME__`            | snake_case, `^[a-z][a-z0-9_]*$`         | `crash_survey`     |
| `__PROJECT_SLUG__`            | kebab-case, `^[a-z][a-z0-9-]*$`         | `crash-survey`     |
| `__PROJECT_DESCRIPTION__`     | free-form one-liner                     | `Survey of crashes` |

What the script does:

- Rewrites every `*.toml`, `*.py`, `*.md`, `*.sbatch`, `*.sh`, `*.ps1`,
  `*.yml`, `*.def`, `Dockerfile*`, and `.env.example` file to replace
  the three tokens.
- Renames `src/__PACKAGE_NAME__/` to `src/<package>/`.
- Deletes itself (`scripts/instantiate.{sh,ps1}`) so the scaffold can
  only be instantiated once.

Non-interactive form (for CI or reproducible bootstraps):

**PowerShell:**

```powershell
.\scripts\instantiate.ps1 -PackageName crash_survey -Slug crash-survey -Description "Survey of crashes"
```

**bash / zsh:**

```bash
bash scripts/instantiate.sh \
    --package-name crash_survey \
    --slug crash-survey \
    --description "Survey of crashes"
```

From here on, `<package>` in any command stands for whatever you just
chose. Nothing in the docs hard-codes the name — read `pyproject.toml`
or `ls src/` if you forget.

## 4. Install dependencies (`pixi install`)

Bring the dev container up and install the Pixi environment. The
initial solve takes 5-10 minutes; subsequent runs hit a persistent
`pixi_env` Docker volume and are instant.

**PowerShell:**

```powershell
docker compose up -d dev
docker compose exec dev pixi install
```

**bash / zsh:**

```bash
docker compose up -d dev
docker compose exec dev pixi install
```

If you prefer host-side Pixi (no Docker) on Linux / macOS, `pixi
install` also works directly from the project root — but the cluster
parity story needs the container, so Docker is the recommended
laptop mode.

## 5. Configure `.env`

**PowerShell:**

```powershell
Copy-Item .env.example .env
```

**bash / zsh:**

```bash
cp .env.example .env
```

Edit `.env`. Replace `<cid>` with your Chalmers ID and `<naiss-id>`
with your NAISS project.

```ini
# Container paths — leave as-is unless you know why.
DATA_DIR=/data
RESULTS_DIR=/results
MODELS_DIR=/models
WORKSPACE_DIR=/workspace
LOG_LEVEL=INFO

# Host bind mounts — leave blank for sibling defaults (../data, ...).
DATA_HOST=
RESULTS_HOST=
MODELS_HOST=

# Cephyr (code) and Mimer (data / weights / results).
CEPHYR_USER=<cid>
CEPHYR_PROJECT_PATH=/cephyr/users/<cid>/Alvis/<project>
CEPHYR_TRANSFER_HOST=vera2.c3se.chalmers.se
ALVIS_LOGIN_HOST=alvis2.c3se.chalmers.se
ALVIS_ACCOUNT=<naiss-id>
MIMER_GROUP_PATH=/mimer/NOBACKUP/groups/<naiss-id>
MIMER_PROJECT_PATH=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/<project>

JUPYTER_PORT=7888
```

Then fix the Slurm `--account` placeholder in every sbatch under
`_shared/slurm/`:

```diff
-#SBATCH --account=<PROJECT_ID>
+#SBATCH --account=<naiss-id>
```

Affected files: `_shared/slurm/cpu.sbatch`, `_shared/slurm/gpu-t4.sbatch`,
`_shared/slurm/gpu-a100.sbatch`, `_shared/slurm/vllm-server.sbatch`
(only the ones you actually intend to run need the fix, but fixing all
of them up front avoids surprises).

## 6. Smoke-check locally (`pixi run smoke` / `pixi run info`)

Run the two canonical tasks. They have zero external dependencies —
all they do is print CPU / GPU / Python info and write a manifest.

**PowerShell:**

```powershell
docker compose exec dev pixi run smoke
docker compose exec dev pixi run info
Get-Content ..\results\manifest-*.json | Select-Object -First 40
```

**bash / zsh:**

```bash
docker compose exec dev pixi run smoke
docker compose exec dev pixi run info
head -n 40 ../results/manifest-*.json
```

Expected: a JSON manifest appears at `$RESULTS_DIR/manifest-<ts>.json`,
the paths resolve to `/data`, `/results`, `/models`, and the `runtime`
section shows `in_slurm: false`. On a laptop the `gpu` array is empty
unless you un-commented the nvidia block in `docker-compose.yml`.

The canonical Pixi task set is fixed across every V3SE project:

| Task             | What it does                                |
|------------------|---------------------------------------------|
| `pixi run smoke` | Collect + print + persist the run manifest |
| `pixi run info`  | Dump the manifest to stdout (no write)     |
| `pixi run test`  | Run pytest over `tests/`                   |
| `pixi run lint`  | Bytecode-compile `src/`, `scripts/`, `tests/` |

## 7. Optional Docker / Apptainer build (local SIF)

If you have Apptainer on WSL2 / Linux and want to verify the SIF mode
before pushing to the cluster:

**bash / zsh:**

```bash
apptainer build dev.sif apptainer/dev.def
apptainer run --bind .:/workspace dev.sif pixi install
apptainer run --bind .:/workspace dev.sif pixi run smoke
```

On macOS / Windows without local Apptainer, skip this step — the
Alvis-side build in section 10 covers the SIF mode.

Two recipes ship in `apptainer/`:

- `dev.def` — the dev loop image (same layers used by docker-compose).
- `app.def` — a thin runtime image used for packaging the final app
  (see [container-modes.md](container-modes.md)).

## 8. First run locally

For the blank scaffold, "the first run" is just `pixi run smoke` in
the container; you ran it in section 6. Replace `scripts/smoke.py`
with your entrypoint when you bolt on real work, and keep the
manifest — it's a cheap provenance record.

To develop interactively inside the container:

**PowerShell:**

```powershell
docker compose exec dev bash
# inside:
pixi shell
python -c "from <package>.manifest import build_manifest; import json; print(json.dumps(build_manifest(), indent=2))"
```

**bash / zsh:**

```bash
docker compose exec dev bash
# inside:
pixi shell
python -c "from <package>.manifest import build_manifest; import json; print(json.dumps(build_manifest(), indent=2))"
```

To add a new entrypoint:

1. Write `scripts/my_task.py` — keep it thin; put logic in `src/<package>/`.
2. Add a line under `[tasks]` in `pixi.toml`:
   ```toml
   my_task = "python scripts/my_task.py"
   ```
3. Run it: `pixi run my_task`.

## 9. Push code to Cephyr

### Git (preferred)

**PowerShell / bash / zsh:**

```bash
git init -b main
git add .env.example .gitignore pixi.toml pyproject.toml README.md \
        _shared/ apptainer/ configs/ docker-compose.yml docs/ scripts/ \
        src/ tests/
git commit -m "initial <project> scaffold"
git remote add origin git@github.com:<team>/<project>.git
git push -u origin main
```

Then on the cluster:

```bash
ssh <cid>@alvis2.c3se.chalmers.se
mkdir -p /cephyr/users/<cid>/Alvis
cd /cephyr/users/<cid>/Alvis
git clone git@github.com:<team>/<project>.git
cd <project>
```

Copy your `.env` (never committed) from laptop to cluster.

**PowerShell:**

```powershell
scp .env <cid>@vera2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/<project>/.env
```

**bash / zsh:**

```bash
scp .env <cid>@vera2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/<project>/.env
```

### rsync (fallback — solo workflow, no remote)

Use the shipped helper from the laptop:

**PowerShell:**

```powershell
bash .\_shared\scripts\sync-to-cephyr.sh
```

**bash / zsh:**

```bash
bash ./_shared/scripts/sync-to-cephyr.sh
```

It reads `CEPHYR_USER` / `CEPHYR_PROJECT_PATH` from `.env` and rsyncs
the tree over `vera2.c3se.chalmers.se`, excluding `.git`, `.pixi`,
`results/`, and `models/`.

## 10. First sbatch submission on Alvis

SSH to Alvis and build the dev SIF. Point the Apptainer cache at
Mimer to avoid hammering your 30 GiB / 60k-file Cephyr quota.

**bash / zsh (on Alvis):**

```bash
ssh <cid>@alvis2.c3se.chalmers.se
cd /cephyr/users/<cid>/Alvis/<project>

export APPTAINER_CACHEDIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/apptainer-cache
mkdir -p "$APPTAINER_CACHEDIR"

apptainer build dev.sif apptainer/dev.def
```

First build: 2-5 minutes. The resulting `dev.sif` is ~700 MB — it
lives in your Cephyr checkout, so keep an eye on quota with
`C3SE_quota`. See [sif-management.md](sif-management.md) if quota
becomes tight.

Then submit the CPU job first — fastest and exercises bind mounts
without needing a GPU queue slot:

```bash
sbatch _shared/slurm/cpu.sbatch
squeue -u $USER                     # wait for R, then CG
cat slurm-cpu-job-*.out
```

Expected: the manifest JSON echoes with paths `/data`, `/results`,
`/models`, and `runtime.in_slurm: true`.

Then the T4 GPU job:

```bash
sbatch _shared/slurm/gpu-t4.sbatch
squeue -u $USER
cat slurm-gpu-t4-smoke-*.out
```

Expected: `runtime.in_slurm: true` AND `gpu` contains one entry with
`name: "Tesla T4"`, memory ~15 GB. If `gpu` is empty despite the T4
allocation, the `--nv` flag is probably missing from the sbatch's
`apptainer run` line.

## 11. Pull results back

From the laptop, pull `results/` back. The manifest files are tiny
(KB-scale), so rsync finishes in seconds.

**PowerShell:**

```powershell
rsync -avh --progress `
  <cid>@vera2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/<project>/results/ `
  .\results\
```

**bash / zsh:**

```bash
rsync -avh --progress \
  <cid>@vera2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/<project>/results/ \
  ./results/
```

Or use the helper:

**PowerShell:**

```powershell
bash .\_shared\scripts\sync-from-cephyr.sh
```

**bash / zsh:**

```bash
bash ./_shared/scripts/sync-from-cephyr.sh
```

Inspect any manifest:

**PowerShell:**

```powershell
Get-Content .\results\manifest-*.json | Select-String '"name"'
```

**bash / zsh:**

```bash
jq '.gpu, .runtime' results/manifest-*.json
```

## 12. Iterate

The tight loop, once the three modes are all green:

```
1. Edit on laptop.
2. docker compose exec dev pixi run smoke     # confirm it runs locally.
3. bash ./_shared/scripts/sync-to-cephyr.sh   # or git push / git pull on Alvis.
4. ssh alvis2 "cd <path>; apptainer build dev.sif apptainer/dev.def"
   (rebuild only if apptainer/dev.def or deps changed).
5. ssh alvis2 "cd <path>; sbatch _shared/slurm/gpu-t4.sbatch".
6. Wait for the job. Read the .out file.
7. Rsync results back to laptop.
```

Verification checklist before you graduate to a real workload:

- [ ] `.env` is filled in and NOT committed (check `git status`).
- [ ] `scripts/instantiate.{sh,ps1}` are gone (the script deletes them).
- [ ] `src/<package>/` exists and no file anywhere still contains a
      literal `__PACKAGE_NAME__` / `__PROJECT_SLUG__` /
      `__PROJECT_DESCRIPTION__` token.
- [ ] Every sbatch you intend to run has your real `--account=<naiss-id>`.
- [ ] Docker smoke wrote `../results/manifest-*.json` with `in_slurm: false`.
- [ ] `apptainer build dev.sif apptainer/dev.def` on Alvis completed
      and `ls -lh dev.sif` shows a ~500 MB-2 GB file.
- [ ] `APPTAINER_CACHEDIR` pointed at Mimer during the build (check
      `C3SE_quota` — Cephyr should not have grown by the cache size).
- [ ] `_shared/slurm/cpu.sbatch` job reached state `CG`/`CD` and the
      `.out` file contains a manifest with `in_slurm: true`.
- [ ] `_shared/slurm/gpu-t4.sbatch` manifest lists a Tesla T4 in the
      `gpu` array.
- [ ] `results/` synced back to the laptop and every manifest opens.

## 13. What's next

Once the smoke is green in all three modes, you have a working V3SE
project. From here:

- Replace `scripts/smoke.py` with your real entrypoint.
- Add dependencies to `pixi.toml` under `[dependencies]` /
  `[pypi-dependencies]`.
- Extend `src/<package>/` with your actual code and wire it from a new
  Pixi task under `[tasks]`.
- See [modification.md](modification.md) for the full adapt-to-your-
  project checklist.
- See [cluster-workflow.md](cluster-workflow.md) for the rsync + ssh +
  sbatch loop in depth.
- See [data-patterns.md](data-patterns.md) for how to plug in HF
  models, datasets on Mimer, and the shared HuggingFace hub mirror.
- See [sif-management.md](sif-management.md) for keeping Cephyr quota
  under control as you iterate on the SIF.
- See [troubleshooting.md](troubleshooting.md) when something
  mysterious happens.

For a library of worked examples that extend this scaffold with
specific capabilities (HF inference, LoRA training, vLLM serving,
multi-GPU, etc.), see the sibling `v3se-examples/` tree.
