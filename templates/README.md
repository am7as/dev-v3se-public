# templates

A single-repo, public/shareable **project scaffold** for Chalmers
C3SE's environment (Alvis GPU cluster + Cephyr storage).

It teaches *cluster resource utilization* — how to structure a project
so the same code runs in three modes (local Docker, local Apptainer,
Alvis Apptainer via Slurm) while respecting the cluster's quota,
container, and storage rules.

> For a **library of 10 worked examples** (tier1 basics → tier3
> advanced) that extend this scaffold, see
> [`../examples/`](../examples/).

## First thing you do

This template ships with three literal placeholder tokens
(`__PACKAGE_NAME__`, `__PROJECT_SLUG__`, `__PROJECT_DESCRIPTION__`).
Un-instantiated code will NOT compile — that's intentional, it forces
you to pick real names before you start writing project code.

### Instantiate

PowerShell (Windows):

```powershell
.\scripts\instantiate.ps1
```

bash / zsh (macOS / Linux):

```bash
bash scripts/instantiate.sh
```

The script prompts for three inputs, substitutes tokens across the
tree, renames `src/__PACKAGE_NAME__/` to your real package, and
deletes itself. Then continue with the rest of this README.

Non-interactive form (for CI):

```powershell
.\scripts\instantiate.ps1 -PackageName crash_survey -Slug crash-survey -Description "Survey of crashes"
```

```bash
bash scripts/instantiate.sh --package-name crash_survey --slug crash-survey --description "Survey of crashes"
```

## What you get

The repo is bootstrapped from a minimal scaffold: a
`pixi run smoke` entry point that prints CPU/GPU/env info and writes a
manifest. Plus:

| Piece                               | Location                              |
|-------------------------------------|---------------------------------------|
| Apptainer recipes (dev + app)       | `apptainer/dev.def`, `apptainer/app.def` |
| Docker compose for laptop dev loop  | `docker-compose.yml`                  |
| Slurm sbatch (CPU, T4, A100, vLLM)  | `_shared/slurm/*.sbatch`              |
| Sync scripts (Cephyr + port-fwd)    | `_shared/scripts/*.sh`                |
| Env contract (DATA_DIR, etc.)       | `_shared/env/.env.template`, `.env.example` |
| Python skeleton                     | `src/__PACKAGE_NAME__/` (renamed by the instantiate script) |
| Smoke + info scripts                | `scripts/smoke.py`, `scripts/info.py` |
| Tests                               | `tests/test_smoke.py`                 |

Reusable cluster infrastructure is in `_shared/` — the single source of
truth for sbatch templates, apptainer base, sync scripts, Dockerfile.

## Quickstart (after you ran the instantiate script)

### PowerShell (Windows)

```powershell
# 1. Clone this template to your own project folder
Copy-Item . ..\my-cluster-project -Recurse
cd ..\my-cluster-project

# 2. Instantiate (substitutes the three tokens across the tree)
.\scripts\instantiate.ps1

# 3. Configure env
Copy-Item .env.example .env
#    Edit .env to set CEPHYR_USER, CEPHYR_PROJECT_DIR, Slurm account.

# 4. Laptop dev loop
docker compose up -d dev
docker compose exec dev pixi install
docker compose exec dev pixi run smoke

# 5. Local Apptainer (matches Alvis execution)
apptainer build dev.sif apptainer/dev.def
apptainer run --bind .:/workspace dev.sif pixi run smoke

# 6. Rsync to Cephyr and sbatch on Alvis
bash ./_shared/scripts/sync-to-cephyr.sh
ssh <cid>@alvis2.c3se.chalmers.se
cd /cephyr/users/<cid>/Alvis/my-cluster-project
sbatch ./_shared/slurm/gpu-t4.sbatch
```

### Bash / zsh (macOS / Linux)

```bash
# 1. Clone this template to your own project folder
cp -r . ../my-cluster-project
cd ../my-cluster-project

# 2. Instantiate (substitutes the three tokens across the tree)
bash scripts/instantiate.sh

# 3. Configure env
cp .env.example .env
#    Edit .env to set CEPHYR_USER, CEPHYR_PROJECT_DIR, Slurm account.

# 4. Laptop dev loop
docker compose up -d dev
docker compose exec dev pixi install
docker compose exec dev pixi run smoke

# 5. Local Apptainer (matches Alvis execution)
apptainer build dev.sif apptainer/dev.def
apptainer run --bind .:/workspace dev.sif pixi run smoke

# 6. Rsync to Cephyr and sbatch on Alvis
bash ./_shared/scripts/sync-to-cephyr.sh
ssh <cid>@alvis2.c3se.chalmers.se
cd /cephyr/users/<cid>/Alvis/my-cluster-project
sbatch ./_shared/slurm/gpu-t4.sbatch
```

## The C3SE resource-utilization contract

Every project cloned from this template promises to:

- **Container paths fixed**: `/workspace`, `/data`, `/results`, `/models`.
- **Env-driven host paths**: `${DATA_HOST:-../sibling-data}` style — same code runs on laptop and cluster.
- **`HF_HOME` never at `$HOME`**: set to project-local or `/tmp/hf-cache` — Cephyr quota is 30 GiB **and** 60k files.
- **Models in SIFs**, not unpacked trees (file-count suicide).
- **Every sbatch has `--account=<PROJECT_ID>`** placeholder.
- **Canonical pixi tasks present**: `smoke`, `info`, `test`, `lint`.

These rules come from C3SE's documented policies. Read:

| Topic                          | Doc                                        |
|--------------------------------|--------------------------------------------|
| Alvis + Cephyr in 10 minutes   | [docs/c3se-primer.md](docs/c3se-primer.md)     |
| Quota-safe SIF management      | [docs/sif-management.md](docs/sif-management.md) |
| rsync + ssh + sbatch loop      | [docs/cluster-workflow.md](docs/cluster-workflow.md) |
| Data source patterns           | [docs/data-patterns.md](docs/data-patterns.md) |
| Dev vs deployment containers   | [docs/container-modes.md](docs/container-modes.md) |
| This scaffold, piece by piece  | [docs/structure.md](docs/structure.md)     |
| First-time setup               | [docs/setup.md](docs/setup.md)             |
| Step-by-step usage             | [docs/usage.md](docs/usage.md)             |
| Adapting to your project       | [docs/modification.md](docs/modification.md) |
| When things go wrong           | [docs/troubleshooting.md](docs/troubleshooting.md) |

## What to change to make this yours

See [docs/modification.md](docs/modification.md). In short:

1. Run the instantiate script — that handles the three-token rename.
2. Set `--account=<PROJECT_ID>` in every sbatch you'll use from `_shared/slurm/`.
3. Fill in `.env` (copy from `.env.example`).
4. Add your real dependencies to `pixi.toml`.
5. Extend `src/<pkg>/` with your actual code.

## What this template does NOT include

- **No AI model or real dataset** — that's by design. Start with green
  smoke tests, then add one layer at a time.
- **No distributed training / multi-provider routing** — see
  [`../examples/`](../examples/) for
  worked examples of those patterns.
