# Modification — making the template your own

What to change, what to leave alone, and where to add new capabilities.

## Rename the project

This template ships with three placeholder tokens
(`__PACKAGE_NAME__`, `__PROJECT_SLUG__`, `__PROJECT_DESCRIPTION__`).
They are substituted in one shot by the instantiation script:

PowerShell (Windows):

```powershell
.\scripts\instantiate.ps1
```

bash / zsh (macOS / Linux):

```bash
bash scripts/instantiate.sh
```

The script prompts for three inputs, validates them, substitutes tokens
across the tree, renames `src/__PACKAGE_NAME__/` to your real package,
and deletes itself.

Do NOT edit `pixi.toml`, `pyproject.toml`, or `src/__PACKAGE_NAME__/`
by hand before running the script — the tokens are load-bearing.

## Adding Python dependencies

Edit `pixi.toml`:

```toml
[dependencies]
python = "3.12.*"
numpy  = "*"

[pypi-dependencies]
<your-pkg>    = { path = ".", editable = true }
transformers = "*"
```

Then inside the container:

PowerShell (Windows):

```powershell
docker compose exec dev pixi install
```

bash / zsh (macOS / Linux):

```bash
docker compose exec dev pixi install
```

On Alvis: rebuild `dev.sif` (Pixi is inside the image; deps resolve at
`pixi install` time which runs inside `%post` of `app.def` or on-demand
in `dev.def`).

## Adding a GPU dependency

If you're adding torch:

1. `pixi.toml`:
   ```toml
   [pypi-dependencies]
   torch = { version = "*", index = "https://download.pytorch.org/whl/cu121" }
   ```
2. Re-resolve: `docker compose exec dev pixi install`.
3. In `docker-compose.yml`, uncomment the `deploy.resources.devices` block
   (laptop must have NVIDIA Container Toolkit + compatible Windows/WSL2 or
   Linux setup).
4. On Alvis, `apptainer run --nv ...` exposes GPU to the container
   (already done in `slurm/gpu-smoke.sbatch`).

## Adding a new data source

The template reads data from `$DATA_DIR`. To swap where that maps from:

- **Laptop**: set `DATA_HOST=/path/to/other/data` in `.env`, then
  `docker compose down && docker compose up -d`.
- **Alvis**: add a `--bind` in your sbatch script:
  ```bash
  apptainer run --nv \
      --bind /mimer/NOBACKUP/Datasets/mydataset:/data \
      dev.sif pixi run my_task
  ```

Keep container paths (`/data`, `/results`, `/models`) fixed — that's how
code stays portable.

## Adding a new entrypoint

1. `scripts/my_task.py`:
   ```python
   from <your_pkg> import something
   def main(): ...
   if __name__ == "__main__": main()
   ```
2. Register in `pixi.toml`:
   ```toml
   [tasks]
   my_task = "python scripts/my_task.py"
   ```
3. Run: `pixi run my_task`.

## Adding a new Slurm profile

Copy one of the existing `slurm/*.sbatch` files, change the resource
request, and add the new entrypoint. Example for multi-GPU:

```bash
#SBATCH --gpus-per-node=A100:4
#SBATCH --cpus-per-task=16
#SBATCH --mem=128G
#SBATCH --time=1-00:00:00

apptainer run --nv --bind .:/workspace dev.sif pixi run train_distributed
```

## What NOT to change

- **Container paths**: `/workspace`, `/data`, `/results`, `/models`. Moving
  these breaks downstream templates and the cluster story.
- **Env-var names** read by code: `DATA_DIR`, `RESULTS_DIR`, `MODELS_DIR`,
  `HF_HOME`. Other templates expect these exact names.
- **Pixi task names**: `smoke`, `info`, `test`, `lint`. Keep these even
  when you add more; they're the cross-template contract.
- **Folder structure**: `src/<pkg>/`, `scripts/`, `configs/`, `slurm/`,
  `apptainer/`, `tests/`, `docs/`. If you move things, a future `12-multi-source-data`
  combination template won't merge cleanly.

## Checklist after instantiation

- [ ] `scripts/instantiate.sh` / `scripts/instantiate.ps1` deleted (the
      script removes itself after running).
- [ ] No `__PACKAGE_NAME__` / `__PROJECT_SLUG__` / `__PROJECT_DESCRIPTION__`
      tokens remain anywhere in the tree.
- [ ] `.env.example` augmented with template-specific keys.
- [ ] At least one new `pixi run` task with a real entrypoint.
- [ ] `tests/test_smoke.py` updated to import your package's new modules.
- [ ] `docs/` updated — describe your actual project.
- [ ] Slurm `--account=<PROJECT_ID>` set to your C3SE project id (this
      placeholder is a separate, run-time placeholder — not a token).
- [ ] Smoke test green in Docker, laptop Apptainer, and Alvis Apptainer.
