# Troubleshooting — `01-foundation`

The errors most likely to hit, with fixes.

## Docker Compose

### `error: bind source path does not exist: ../data`

The default host paths are siblings of the project. Either create them:

```powershell
New-Item -ItemType Directory -Path ..\data, ..\results, ..\models -Force | Out-Null
```

Or override in `.env` to point somewhere else:

```ini
DATA_HOST=D:/mydata
```

Then `docker compose down && docker compose up -d dev`.

### `pixi install` is slow / stuck

Pixi resolves environments once and caches. The first install is 1–3
minutes. Subsequent `pixi install` calls should be sub-second.

If it hangs: check `docker compose logs dev`. Common cause is no
internet inside the container — verify with `docker compose exec dev curl -I https://conda-forge.org/`.

### Changes to `.env` don't seem to apply

Docker reads `.env` at container-create time, not on every exec.

```powershell
docker compose down
docker compose up -d dev
```

## Apptainer

### `FATAL: could not use fakeroot: no user namespace mappings`

Apptainer wants user namespaces for building on laptop. Two workarounds:

1. Build the image on Alvis login node instead:
   ```bash
   ssh alvis2 "cd /cephyr/users/<cid>/Alvis/__PROJECT_SLUG__ && apptainer build dev.sif apptainer/dev.def"
   ```
2. Build on Linux-proper or WSL2 with user-namespace support enabled.

### `nvidia-smi: command not found` inside the SIF

You forgot `--nv`:

```bash
apptainer run --nv --bind .:/workspace dev.sif pixi run smoke
```

Without `--nv`, the container has no access to GPU drivers or
`nvidia-smi`, so `gpu_info()` returns `[]`.

### `bash: pixi: command not found`

The base image (`ghcr.io/prefix-dev/pixi`) ships pixi in
`/opt/pixi/bin`. Confirm it's on `PATH`:

```bash
apptainer exec dev.sif bash -c 'echo $PATH; which pixi'
```

If missing, the `%environment` block of the `.def` file didn't apply —
rebuild the SIF.

## Alvis / Slurm

### Job stays in PD (pending) forever

```bash
squeue -u $USER -o "%i %T %r"
```

The `%r` column shows the reason. Common:

- `Priority` / `Resources` — just queue wait. T4 typically < 5 min,
  A100 minutes to hours.
- `AssocGrpCpuLimit` — you've hit your group's CPU-hour quota.
- `QOSMaxJobsPerUserLimit` — too many jobs submitted; cancel some.

### Job runs but the `.out` file is empty

Apptainer is usually running, but your entrypoint failed silently. Check
the `.err` file:

```bash
cat slurm-__PROJECT_SLUG__-*.err
```

Most frequent: `pixi: command not found` (see above) or the SIF path is
wrong (see `SIF=${SIF:-./dev.sif}` in the sbatch — make sure it exists).

### `C3SE_quota: ERROR: too many files`

You've approached 60,000 files in your Cephyr home. Find the worst
offender:

```bash
find /cephyr/users/<cid>/Alvis -xdev -type f | wc -l
du --inodes -d 2 /cephyr/users/<cid>/Alvis | sort -n | tail -20
```

Common culprits: a synced `.pixi/` or `.venv/`. Solution: the
`sync-to-cephyr.sh` script already excludes these. If you synced
manually, `rm -rf` the offenders on Cephyr.

### "You did not use all allocated GPUs"

You requested `--gpus-per-node=T4:2` but only used 1. Change the
request to `T4:1`, or actually use both. C3SE flags wasteful use.

### Result JSON is empty or missing

Two common causes:

1. `RESULTS_DIR` isn't writable. Check permissions on `/results`
   inside the container (`ls -la /results` from inside). If it's
   root-owned and read-only, you're running a deployment SIF without
   binding a writable results path. Fix:
   ```bash
   apptainer run --nv --bind .:/workspace --bind ./results:/results app.sif ...
   ```
2. The script crashed before `write_manifest()`. Check the `.err` file.

## Environment drift (laptop vs Alvis produce different manifests)

Expected — the manifest is intentionally a snapshot of where it runs. A
meaningful drift is:

| Field              | Meaning of mismatch                               |
|--------------------|---------------------------------------------------|
| `cpu.system`       | `Linux` on both (container is Linux). If you see different, something is very wrong. |
| `gpu`              | Empty on laptop without GPU; populated on Alvis. |
| `runtime.in_slurm` | `false` on laptop, `true` on Alvis.              |
| `env.CUDA_VISIBLE_DEVICES` | Blank on laptop, set by Slurm on Alvis. |

If `gpu` is empty on Alvis: `--nv` missing.

## Still stuck

- `docs/../../../docs/c3se-primer.md` — cluster fundamentals + checklists.
- `docs/../../../docs/cluster-workflow.md` — sync + sbatch detail.
- C3SE support: <support@c3se.chalmers.se>
- C3SE docs index: <https://www.c3se.chalmers.se/documentation/>
