# Job lifecycle — sbatch, monitor, debug, retrieve

What happens between "I pushed my code to Cephyr" and "I have my
results back".

## Submit

```bash
ssh alvis
cd /cephyr/users/<cid>/Alvis/<project>
sbatch slurm/gpu-t4.sbatch
# Submitted batch job 123456
```

Every project's `slurm/*.sbatch` should have:

- `#SBATCH --account=<PROJECT_ID>` — **your NAISS account** (replace
  the placeholder)
- `#SBATCH --partition=alvis`
- `#SBATCH --job-name=<something-useful>`
- `#SBATCH --output=slurm-%x-%j.out` / `--error=slurm-%x-%j.err`
- `#SBATCH --time=…`, `--gpus-per-node=T4:1` or `A100:N`,
  `--cpus-per-task=N`, `--mem=NG`

Tip: start with `T4:1` for smoke tests. Don't allocate A100s before
a green T4 run.

## Monitor

```bash
squeue -u $USER                             # your queue
squeue -u $USER -o "%i %T %N %R"           # jobid, state, node, reason

# While running:
tail -f slurm-<jobname>-<jobid>.out

# Post-mortem:
sacct -j <jobid> --format=JobID,State,ExitCode,Elapsed,MaxRSS
```

States you'll see:
- **PD** (pending) — in queue
- **R** (running)
- **CG** (completing) — finishing up
- **CD** (completed) — clean exit
- **F** / **TO** / **CA** (failed / timed-out / cancelled) — look at `.err`

## Interactive debugging

When batch isn't enough — you want a live shell on a GPU node:

```bash
srun --account=<PROJECT_ID> --partition=alvis -t 0-01:00:00 \
     --gpus-per-node=T4:1 --cpus-per-task=4 --mem=16G --pty bash

# You're now on a compute node.
cd /cephyr/users/<cid>/Alvis/<project>
apptainer shell --nv dev.sif
# Inside the SIF:
pixi run smoke
```

`--pty bash` gives you an interactive shell; the allocation ends
when you `exit`.

## Port-forwarding a running job to laptop

For Jupyter, vLLM, LM Studio, Ollama, TensorBoard — anything serving
HTTP from a compute node:

1. **On cluster**: the job writes its host:port to `$RESULTS_DIR`
   (e.g. `ollama-host.txt`, `ollama-port.txt`). That's the convention
   in the 06/07/11 templates.
2. **On laptop**:

**PowerShell:**

```powershell
# Read host:port from the job output (after rsync'ing results),
# or find directly:
ssh alvis cat /cephyr/users/<cid>/Alvis/<project>/results/ollama-host.txt
ssh alvis cat /cephyr/users/<cid>/Alvis/<project>/results/ollama-port.txt

# Forward
ssh -L 11434:<compute-node>:11434 <cid>@alvis2.c3se.chalmers.se
# Then in another PowerShell:
$env:OPENAI_BASE_URL="http://localhost:11434/v1"
pixi run infer --prompt "Hello"
```

**bash / zsh:**

```bash
HOST=$(ssh alvis cat /cephyr/users/<cid>/Alvis/<project>/results/ollama-host.txt)
PORT=$(ssh alvis cat /cephyr/users/<cid>/Alvis/<project>/results/ollama-port.txt)
ssh -L $PORT:$HOST:$PORT <cid>@alvis2.c3se.chalmers.se
# Then:
OPENAI_BASE_URL=http://localhost:$PORT/v1 pixi run infer --prompt "Hello"
```

Project templates ship `_shared/scripts/port-forward.sh` that wraps
this — point it at a job id and it handles the rest.

## Cancelling

```bash
scancel <jobid>                  # cancel one
scancel -u $USER                 # cancel all your jobs (careful)
```

## Typical edit → submit → retrieve loop

**Laptop terminal 1 (persistent):**

```bash
bash _shared/scripts/sync-to-cephyr.sh && \
  ssh alvis "cd /cephyr/users/<cid>/Alvis/<project> && sbatch slurm/gpu-t4.sbatch"
```

**Laptop terminal 2 (observe):**

```bash
ssh alvis "tail -F /cephyr/users/<cid>/Alvis/<project>/slurm-*.out"
```

**After it finishes** — pull back:

```bash
rsync -avh <cid>@alvis2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/<project>/results/ ./results/
rsync -avh <cid>@alvis2.c3se.chalmers.se:/mimer/NOBACKUP/groups/<naiss-id>/<cid>/<project>/checkpoints/ ./checkpoints/
```
