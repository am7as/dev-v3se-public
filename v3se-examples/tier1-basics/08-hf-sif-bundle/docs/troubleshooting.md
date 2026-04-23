# Troubleshooting — `08-hf-sif-bundle`

Issues listed by symptom. Each has a short diagnosis and the exact
commands to fix it. Build-time and run-time failures are mixed
intentionally — most users hit build issues first.

## 1. SIF build fails with `401 Unauthorized`

**Symptom** — during `apptainer build`, the `%post` step errors:

```
401 Client Error: Unauthorized for url:
  https://huggingface.co/api/models/meta-llama/Llama-3.2-3B-Instruct
```

**Cause** — the model is gated and you either didn't set `HF_TOKEN`
or didn't accept the license on the HuggingFace model page.

**Fix** —

1. Visit `https://huggingface.co/<org>/<name>` and click "Agree and
   access". Wait for approval if the repo requires manual review.
2. Generate a **read** token at
   <https://huggingface.co/settings/tokens>.
3. Add to `.env`:

   ```ini
   HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxx
   ```

4. Rebuild:

   ```bash
   rm model.sif
   bash scripts/build-model-sif.sh
   ```

Confirm the token works outside Apptainer first:

```bash
curl -fsSL -H "Authorization: Bearer $HF_TOKEN" \
    https://huggingface.co/api/whoami-v2
```

## 2. SIF build fails with `429 Too Many Requests`

**Symptom** — `huggingface-cli download` during `%post` returns:

```
HTTPError: 429 Client Error: Too Many Requests
```

**Cause** — unauthenticated HF downloads have a tight rate limit;
you hit it from a shared NAT on Alvis or from iterating builds.

**Fix** — either wait 5–10 minutes and retry, or authenticate (the
higher rate-limit tier):

```ini
# .env
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxx
```

Even for **public** models, setting `HF_TOKEN` raises your limit.

## 3. SIF build fails with `no space left on device`

**Symptom** — build aborts mid-`%post`, often during
`huggingface-cli download` or `pip install torch`.

**Cause** — `APPTAINER_CACHEDIR` defaults to `$HOME/.apptainer/`
which is Cephyr (30 GiB cap). A 7 B model + CUDA base layers easily
burns through that.

**Fix** — redirect the cache to Mimer **before** building:

```bash
ssh alvis
export APPTAINER_CACHEDIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/apptainer-cache
mkdir -p "$APPTAINER_CACHEDIR"

# Clean up any partial build on Cephyr
rm -rf ~/.apptainer/cache ~/.apptainer/tmp

# Persist for future sessions
echo "export APPTAINER_CACHEDIR=$APPTAINER_CACHEDIR" >> ~/.bashrc
```

Also redirect temp:

```bash
export APPTAINER_TMPDIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/apptainer-tmp
mkdir -p "$APPTAINER_TMPDIR"
```

Then re-run `bash scripts/build-model-sif.sh`.

## 4. Cephyr quota exhaustion after several builds

**Symptom** — `C3SE_quota` shows Cephyr near 100% even though you
moved the cache to Mimer. Or `git` commands start failing with
"disk quota exceeded".

**Cause** — leftover SIFs, failed builds, or `results/` accidentally
landed on Cephyr.

**Fix** — find and relocate:

```bash
ssh alvis
du -sh /cephyr/users/<cid>/Alvis/* 2>/dev/null | sort -h | tail

# Move built SIFs to Mimer
mv /cephyr/users/<cid>/Alvis/<project>/*.sif \
   /mimer/NOBACKUP/groups/<naiss-id>/<cid>/sifs/

# Symlink the primary one back for sbatch convenience
ln -sf /mimer/NOBACKUP/groups/<naiss-id>/<cid>/sifs/model.sif \
       /cephyr/users/<cid>/Alvis/<project>/model.sif

# Move results
mv /cephyr/users/<cid>/Alvis/<project>/results \
   /mimer/NOBACKUP/groups/<naiss-id>/<cid>/<project>/results
ln -sf /mimer/NOBACKUP/groups/<naiss-id>/<cid>/<project>/results \
       /cephyr/users/<cid>/Alvis/<project>/results
```

Set `RESULTS_DIR` to the Mimer path in `.env` so new jobs never hit
Cephyr.

## 5. Run-time: `MODEL_DIR=/opt/model not found`

**Symptom** — `RuntimeError: MODEL_DIR=/opt/model not found. This
example expects a SIF with weights baked in. Build it first: bash
scripts/build-model-sif.sh`

**Cause** — you're running `dev.sif` (no weights baked) instead of
`model.sif`. The stock `slurm/gpu-t4.sbatch` points at `./dev.sif`.

**Fix** — either override `SIF`:

```bash
sbatch --export=ALL,SIF=./model.sif,PROMPT="Hello" slurm/gpu-t4.sbatch
```

Or edit the sbatch to default to `model.sif`:

```diff
-SIF="${SIF:-./dev.sif}"
+SIF="${SIF:-./model.sif}"
```

Or, on laptop, directly:

```bash
apptainer run --nv model.sif "Hello"
```

## 6. Job runs on CPU despite requesting a GPU

**Symptom** — `smoke.json` shows `cuda_available: false`, or
generation takes minutes instead of seconds.

**Cause** — missing `--nv` on the `apptainer run` line.

**Fix** — every cluster `apptainer run` MUST include `--nv`:

```bash
grep apptainer slurm/*.sbatch   # should show --nv on every line
```

```diff
-apptainer run --bind .:/workspace "$SIF" pixi run infer --prompt "$PROMPT"
+apptainer run --nv --bind .:/workspace "$SIF" pixi run infer --prompt "$PROMPT"
```

## 7. `HF_HOME` leaking to `$HOME`

**Symptom** — Cephyr quota jumps unexpectedly; `du -sh ~/.cache/`
shows multi-GiB.

**Cause** — `transformers` falls back to `$HOME/.cache/huggingface`
when `HF_HOME` is unset. Even for a baked SIF, `AutoTokenizer` /
`AutoModel` may create lock files or side-caches there.

**Fix** — point `HF_HOME` at Mimer, in `.env`:

```ini
HF_HOME=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/<project>/.hf-cache
```

The sbatch already exports `HF_HOME` from `.env`. For belt-and-braces,
inside `apptainer/model.def` `%environment`:

```
export HF_HOME=/tmp/.hf-cache
```

(Inside the container `$HOME` is the invoker's home, so this matters
when running outside Slurm too.)

## 8. Cluster job pending forever

**Symptom** — `squeue -u $USER` shows job in `PD` for hours.

**Cause / fix** — depends on the `Reason` column:

```bash
squeue -u $USER -o "%.18i %.9P %.8j %.2t %.10M %.6D %R"
```

| Reason | Fix |
|--------|-----|
| `Priority` | wait; or drop from `A100:1` to `T4:1`; or shorten `--time` |
| `Resources` | same — ease the reservation |
| `QOSGrpCPULimit` | NAISS project over fair-share; throttle concurrent jobs |
| `AssocMaxJobsLimit` | too many jobs already queued; cancel extras |
| `BadConstraints` | requested a GPU type that doesn't exist — check `sinfo -o "%P %G"` |

For a first-run SIF, always start with `T4:1`.

## 9. First run is very slow; second run is fast

**Symptom** — first `sbatch` takes 2–3 minutes before producing
text; subsequent jobs finish in seconds.

**Cause** — not a bug. Apptainer extracts the SIF to a scratch
location and reads weights through the page cache. The first job
cold-reads multi-GiB of weights from disk; later jobs hit the cache.

**Fix** — nothing. If cold-start matters (short-lived batch jobs),
keep the SIF on a fast filesystem (Mimer) and ensure `/tmp` is
local SSD, not a network mount.

## 10. `apptainer build` hangs at "Copying blob"

**Symptom** — the build sits on `Copying blob <sha>` for many minutes
with no progress.

**Cause** — network stall pulling the `nvidia/cuda` base image from
Docker Hub. Docker Hub rate-limits unauthenticated pulls.

**Fix** —

```bash
# Preferred: build on the Alvis login node (fast network to Docker Hub)
ssh alvis
cd /cephyr/users/<cid>/Alvis/<project>
bash scripts/build-model-sif.sh

# If you must build on laptop: authenticate to Docker Hub
apptainer remote login --username <dockerhub-user> docker://docker.io
```

Or pre-pull the base layer to `$APPTAINER_CACHEDIR` while you have
network, then re-run the build (it'll reuse the cache).
