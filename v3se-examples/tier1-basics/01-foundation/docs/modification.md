# Modification — making the template your own

What to change, what to leave alone, and where to add new capabilities.

## Rename the project

1. **Choose a package name.** Python packages should be `snake_case`, ≤20
   chars, no dots. Example: `crash_survey`.

2. **Rename the source folder**:
   ```powershell
   Rename-Item src\foundation src\<your_pkg>
   ```

3. **Update `pyproject.toml`**:
   ```toml
   [project]
   name = "<your-pkg>"
   authors = [{ name = "Your Lab", email = "contact@example.com" }]

   [tool.hatch.build.targets.wheel]
   packages = ["src/<your_pkg>"]
   ```

4. **Update `pixi.toml`**:
   ```toml
   [workspace]
   name = "<your-pkg>"

   [pypi-dependencies]
   <your-pkg> = { path = ".", editable = true }
   ```

5. **Fix imports in `scripts/*.py` and `tests/*.py`**:
   ```
   from foundation import ...   →   from <your_pkg> import ...
   ```

6. **Update container images names in `docker-compose.yml` and both
   Apptainer `.def` files** (just cosmetic, but nice for logs).

7. `docker compose build` (new image), then
   `docker compose exec dev pixi install` (editable re-install).

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

```powershell
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

## Checklist when moving from foundation → your project

- [ ] Package renamed, all imports updated.
- [ ] `pyproject.toml` + `pixi.toml` authors + description updated.
- [ ] `.env.example` augmented with template-specific keys.
- [ ] At least one new `pixi run` task with a real entrypoint.
- [ ] `tests/test_smoke.py` updated to import your package.
- [ ] `docs/` updated — delete mentions of `foundation`, describe your
      actual project.
- [ ] Slurm `--account` set to your C3SE project.
- [ ] Smoke test green in Docker, laptop Apptainer, and Alvis Apptainer.
