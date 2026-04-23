# Cluster workflow — from laptop to Alvis and back

The end-to-end loop every template supports. Three storage systems
are in play: **Cephyr** (code), **Mimer** (data/weights/results), and
**Alvis** (compute — sees both).

```
 laptop                        Cephyr (code, small)            Alvis compute
┌────────┐     rsync code     ┌──────────────────────┐      ┌──────────────┐
│ edit   │ ──────────────────>│  /cephyr/users/<cid>/│ auto │ sbatch job   │
│ code   │                    │       Alvis/<proj>/  │<─bind│ (apptainer)  │
│        │                    └──────────────────────┘      │              │
│        │                                                  │              │
│        │     rsync data     ┌──────────────────────┐      │              │
│ data/  │ ──────────────────>│  Mimer (big, per-    │ auto │              │
│ weights│                    │  project allocation) │<─bind│              │
│        │<── rsync results ──│  /mimer/NOBACKUP/    │      │              │
│        │                    │       groups/<naiss>/│      └──────────────┘
└────────┘                    └──────────────────────┘
```

## Prerequisites (one-time)

1. **C3SE account** with Alvis allocation. Apply via your PI.
2. **SSH keypair** on laptop, public key registered with C3SE.
3. **SSH config** (highly recommended):
   ```
   # ~/.ssh/config
   Host alvis
     HostName alvis2.c3se.chalmers.se
     User <cid>
     ControlMaster auto
     ControlPath ~/.ssh/control-%r@%h:%p
     ControlPersist yes

   Host cephyr-transfer
     HostName vera2.c3se.chalmers.se
     User <cid>
   ```
4. **On Cephyr**, create a workspace:
   ```bash
   ssh alvis
   mkdir -p /cephyr/users/<cid>/Alvis/projects
   ```

## Step 1 — Develop on laptop

Either Docker dev or Apptainer dev — see [container-modes.md](container-modes.md).

Run `pixi run smoke` locally until green. Don't push to Cephyr until
the smoke test works on your laptop.

## Step 2a — Sync code to Cephyr

Every template ships with `_shared/scripts/sync-to-cephyr.sh`. From the
project root:

```bash
bash _shared/scripts/sync-to-cephyr.sh
```

## Step 2b — Sync data / weights to Mimer (when needed)

Big artefacts — datasets, pre-downloaded weights, existing
checkpoints — belong on Mimer, not Cephyr:

```bash
bash _shared/scripts/sync-to-mimer.sh ./data
bash _shared/scripts/sync-to-mimer.sh ./models/llama-8b models/llama-8b
```

Inside sbatch, bind the Mimer paths over `/data`, `/models`,
`/results`:

```bash
apptainer run --nv \
    --bind $MIMER_GROUP_PATH/data:/data:ro \
    --bind $MIMER_PROJECT_PATH/results:/results \
    --bind $MIMER_PROJECT_PATH/models:/models \
    dev.sif pixi run train
```

Or manually:

```bash
rsync -avh --progress --delete \
  --exclude='.pixi/' --exclude='__pycache__/' --exclude='.venv/' \
  --exclude='results/' --exclude='*.sif' \
  ./  <cid>@vera2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/my-project/
```

Exclusions matter:

- `.pixi/` — rebuilt on Alvis; pushing copies thousands of files.
- `results/` — you'll bring this back, not push it.
- `*.sif` — binary blobs; if you need one on Alvis, build it there.

## Step 3 — Build the SIF on Alvis

SSH in, cd to the project, build:

```bash
ssh alvis
cd /cephyr/users/<cid>/Alvis/my-project
apptainer build dev.sif apptainer/dev.def
```

First build fetches the base layers (a few minutes). Subsequent builds
reuse cache.

## Step 4 — Submit the Slurm job

```bash
sbatch slurm/gpu-t4.sbatch
squeue -u $USER             # is it pending or running?
```

Monitor:

```bash
tail -f slurm-<jobid>.out
```

When it finishes:

```bash
sacct -j <jobid> --format=JobID,State,ExitCode,Elapsed,MaxRSS
```

## Step 5 — Pull results back

Small results (logs, manifests) sit on Cephyr alongside the code:

```bash
rsync -avh --progress \
  <cid>@vera2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/my-project/results/ \
  ./results/
```

Big artefacts (checkpoints, trained weights, evaluation dumps) live on Mimer:

```bash
rsync -avh --progress \
  <cid>@vera2.c3se.chalmers.se:/mimer/NOBACKUP/groups/<naiss-id>/<cid>/<project>/checkpoints/ \
  ./checkpoints/
```

## Interactive debugging on Alvis

When batch submission isn't enough — you want a live shell on a GPU node:

```bash
srun -A <project> -p alvis -t 0-01:00:00 \
     --gpus-per-node=T4:1 --pty bash

# Now you're on a compute node with a T4.
cd /cephyr/users/<cid>/Alvis/my-project
apptainer shell --nv dev.sif
# inside the SIF:
pixi run smoke
```

## Port forwarding (Jupyter, vLLM, TensorBoard)

Template-provided helper:

```bash
bash _shared/scripts/port-forward.sh <jobid> 8888
```

Or manually: find which compute node your job is on, then forward a
port from laptop through the login node:

```bash
# Check where the job is running
squeue -u $USER -o "%i %N %R"
# e.g., 12345 alvis1-37 R
ssh -L 8890:alvis1-37:8888 <cid>@alvis2.c3se.chalmers.se
# open http://localhost:8890 in your laptop browser
```

## VS Code on Alvis

Two options:

1. **OnDemand code-server** (recommended by C3SE for heavy use): via
   the portal at <https://portal.c3se.chalmers.se/>.
2. **Remote-SSH extension** (fine for editing, not for long-running
   terminals): connects directly to `alvis2.c3se.chalmers.se`.

Source: <https://www.c3se.chalmers.se/documentation/software/development/vscode/>

## Golden rules

1. **Smoke-test locally before pushing** — a failed Slurm job costs
   queue time.
2. **Cephyr for code, Mimer for data** — never keep raw model weight
   trees or large datasets on Cephyr (30 GiB / 60k files will die).
3. **Always read `C3SE_quota` before a big sync** — Cephyr is closer
   to its cap than you think. Check Mimer usage in the NAISS portal.
4. **Test with T4** before allocating A100s.
5. **Use all GPUs you allocate** — idle GPU = flagged user.
6. **Set `HF_HOME`** to Mimer project storage, not `$HOME` or Cephyr.
7. **Bake the SIF once** on a login node, use from many sbatch jobs.
   Don't rebuild per job.
