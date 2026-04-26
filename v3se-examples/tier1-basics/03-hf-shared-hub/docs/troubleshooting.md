# Troubleshooting — `03-hf-shared-hub`

Issues listed by symptom. Each has a short diagnosis and the exact
commands to fix it.

## 1. `HF_MODEL_SNAPSHOT is not set`

**Symptom** — `RuntimeError: HF_MODEL_SNAPSHOT is not set. This
example loads from C3SE's shared hub only.` thrown by `load()`
during `pixi run smoke` or `pixi run infer`.

**Cause** — `.env` is missing on the cluster (it's git-ignored, so
it never arrives via `git clone`) or the sbatch didn't source it.

**Fix** — copy `.env` from laptop once, then verify the sbatch
sources it:

**PowerShell:**

```powershell
scp .env <cid>@alvis2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/<project>/.env
```

**bash / zsh:**

```bash
scp .env <cid>@alvis2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/<project>/.env
ssh alvis "grep HF_MODEL_SNAPSHOT /cephyr/users/<cid>/Alvis/<project>/.env"
```

The sbatch already does `[ -f .env ] && { set -a; . ./.env; set +a; }`
— if you removed that line, put it back.

## 2. `HF_MODEL_SNAPSHOT=<path> does not exist`

**Symptom** — load fails with the path you configured, saying it
doesn't exist on disk.

**Cause** — two possibilities: (a) the commit hash in the snapshot
path has changed upstream, (b) the model isn't actually in C3SE's
mirror.

**Fix** — list the mirror and pick a valid hash:

```bash
ssh alvis
# Is the model even mirrored?
ls /mimer/NOBACKUP/Datasets/LLM/huggingface/hub/ | grep -i <your-model>

# Available snapshots for it:
ls /mimer/NOBACKUP/Datasets/LLM/huggingface/hub/models--<org>--<name>/snapshots/

# `main` and `refs` symlinks exist too — prefer a concrete hash for
# reproducibility:
readlink /mimer/NOBACKUP/Datasets/LLM/huggingface/hub/models--<org>--<name>/snapshots/main
```

If no results, the model isn't mirrored. Either request it via C3SE
support or switch to `../08-hf-sif-bundle/`.

## 3. Cephyr quota exhaustion

**Symptom** — `disk quota exceeded` during `apptainer build`, `git
clone`, or when writing `results/`. `C3SE_quota` shows 100% used or
the file count near 60 000.

**Cause** — model weights, apptainer cache, or results accidentally
landed on Cephyr instead of Mimer. The 30 GiB / 60 000-file cap is
small.

**Fix** — redirect caches and results to Mimer:

```bash
ssh alvis
C3SE_quota

# Where does the usage live?
du -sh /cephyr/users/<cid>/Alvis/* 2>/dev/null | sort -h | tail

# Fixes (run as needed)
export APPTAINER_CACHEDIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/apptainer-cache
mkdir -p "$APPTAINER_CACHEDIR"

# Move any stray caches
mv ~/.apptainer "$APPTAINER_CACHEDIR/.apptainer-home" 2>/dev/null || true
mv /cephyr/users/<cid>/Alvis/<project>/results \
   /mimer/NOBACKUP/groups/<naiss-id>/<cid>/<project>/results
ln -sf /mimer/NOBACKUP/groups/<naiss-id>/<cid>/<project>/results \
       /cephyr/users/<cid>/Alvis/<project>/results
```

Set `RESULTS_DIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/<project>/results`
in `.env` so it survives the next run.

## 4. Job runs on CPU despite requesting a GPU

**Symptom** — `smoke` log shows `cuda_available: false`, or the
response text takes minutes instead of seconds.

**Cause** — the `apptainer run` line is missing `--nv`, so the
container can't see the NVIDIA driver — even when Slurm allocated a
GPU.

**Fix** — every cluster `apptainer run` MUST include `--nv`:

```bash
# wrong
apptainer run --bind .:/workspace dev.sif pixi run infer --prompt "..."

# right
apptainer run --nv --bind .:/workspace dev.sif pixi run infer --prompt "..."
```

Check your sbatch:

```bash
grep apptainer slurm/*.sbatch
```

## 5. `HF_HOME` accidentally pointing at `$HOME`

**Symptom** — `~/.cache/huggingface/` balloons, or Cephyr quota
jumps by several GiB unexpectedly, or Hugging Face logs say it's
caching to `/cephyr/users/<cid>/.cache/...`.

**Cause** — `transformers` falls back to `$HOME/.cache/huggingface`
when `HF_HOME` is unset. On Alvis, `$HOME` is on Cephyr (quota-capped).

**Fix** — the sbatch already defaults `HF_HOME=$PWD/.hf-cache` if
unset, but `$PWD` is Cephyr. For anything non-trivial, point
`HF_HOME` at Mimer:

```ini
# .env
HF_HOME=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/<project>/.hf-cache
```

For this example specifically, `HF_HOME` shouldn't matter much —
weights come from the shared mirror via `local_files_only=True`. But
tokenizer cache files and any side-downloads still land there.

## 6. Slurm job pending forever

**Symptom** — `squeue -u $USER` shows the job in `PD` for hours.
`Reason` column shows `Priority`, `Resources`, `QOSGrpCPULimit`, etc.

**Cause / fix** — depends on the `Reason`:

```bash
ssh alvis
squeue -u $USER -o "%.18i %.9P %.8j %.2t %.10M %.6D %R"
```

| Reason | Meaning | Fix |
|--------|---------|-----|
| `Priority` | other jobs ahead of you | wait, or request a smaller GPU (`T4:1` instead of `A100:1`) / shorter walltime |
| `Resources` | no node has the GPU flavour free | same — ease up on the reservation |
| `QOSGrpCPULimit` | your NAISS project is over its fair-share | check `jobinfo` / `projinfo`; throttle concurrent jobs |
| `AssocMaxJobsLimit` | you already have N jobs running | cancel or wait |
| `BadConstraints` / `ReqNodeNotAvail` | GPU flavour requested doesn't exist | `sinfo -o "%P %G"` to see what's actually available |

For a first job, start with `T4:1` — it's the least-contended flavour
on Alvis.

## 7. `pixi install` fails inside the SIF

**Symptom** — `apptainer run ... pixi run infer` errors with
`torch not found` or `module 'infer_hf' has no attribute 'generate'`.

**Cause** — the SIF was built before you changed deps, OR you built
`app.def` (which bakes `pixi install` at build time) and a code
change reshuffled requirements.

**Fix** — rebuild:

```bash
ssh alvis
cd /cephyr/users/<cid>/Alvis/<project>
rm dev.sif
apptainer build dev.sif apptainer/dev.def
```

For `dev.def` (no baking), `pixi install` runs on first `pixi run`
inside the container and caches into the bind-mounted `.pixi/`. If
that dir is corrupt, `rm -rf .pixi/` and retry.

## 8. Results not appearing after the job completes

**Symptom** — `sbatch` returns, `squeue` shows no running job,
`sacct` shows `COMPLETED`, but `results/responses/` is empty.

**Cause** — `RESULTS_DIR` resolved to an in-container path that
wasn't bind-mounted, so the JSON got written inside the ephemeral
container filesystem.

**Fix** — `pixi run info` prints the resolved `results_dir`. From the
login node:

```bash
# What does the container think $RESULTS_DIR is?
apptainer run --bind .:/workspace dev.sif pixi run info
```

If it shows `/results` but your sbatch doesn't bind `/results`, the
writes go into the container and disappear when it exits. Either:

- Add `--bind $PWD/results:/results` to the `apptainer run` line, or
- Set `RESULTS_DIR=$PWD/results` in `.env` so it writes to the
  host-visible path (the default sbatch already does this).
