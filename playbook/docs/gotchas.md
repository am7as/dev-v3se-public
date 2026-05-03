# Common gotchas & recovery

The top errors researchers hit on C3SE and how to unwind them.

## "My job crashed mid-run with disk errors"

Almost always Cephyr quota — 30 GiB or 60,000 files:

```bash
ssh alvis C3SE_quota
ssh alvis "du --inodes -d 2 /cephyr/users/$USER/Alvis | sort -n | tail -10"
```

Usual culprits, in order of likelihood:

1. **`.pixi/` or `.venv/`** got rsync'd up. Delete them on Cephyr
   and re-run; make sure your sync script excludes them.
2. **HF cache** landed in `~/.cache/huggingface/`. Move cache to
   Mimer:
   ```bash
   export HF_HOME=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/hf-cache
   ```
3. **Raw model weight tree** unpacked on Cephyr. Delete, bake into
   a SIF, or load from `/mimer/NOBACKUP/Datasets/LLM/huggingface/hub/`.
4. **Apptainer build cache** at `~/.apptainer/cache/`. Override:
   ```bash
   export APPTAINER_CACHEDIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/apptainer-cache
   ```

## "Slurm says job completed but there are no results"

Check both the `.out` and `.err` files; the job may have crashed
silently because:

- `CUDA_VISIBLE_DEVICES` wasn't set (you forgot `--gpus-per-node`).
- Apptainer ran without `--nv` → no GPU visible.
- `HF_HOME` defaulted to `$HOME` → download failed because of quota.
- The script hit `set -euo pipefail` on an unset env var.

## "`squeue` says PENDING forever"

```bash
squeue -u $USER -o "%i %T %R"
```

The `%R` column tells you why:

- **Priority** — someone else is ahead; wait.
- **Resources** — cluster's full; wait.
- **QOSMaxCpuPerUserLimit / QOSGrpGRES** — you're hitting an
  allocation or concurrency cap.
- **AssocGrpBillingRunMinutes** — you're out of allocated GPU-hours
  for the month.

Check monthly allocation usage in the NAISS portal.

## "I rsync'd to Cephyr but files aren't showing on Alvis"

Cephyr is eventually consistent but usually instant. Verify:

```bash
ssh alvis "ls /cephyr/users/<cid>/Alvis/<project>"
```

If files are missing, re-run the sync with `--verbose` to see what
rsync actually did. Check your `CEPHYR_PROJECT_DIR` in `.env`.

## "Apptainer build fails on login node with 'no space left'"

Apptainer's build cache at `~/.apptainer/cache/` can easily exceed
1 GB. Redirect:

```bash
export APPTAINER_CACHEDIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/apptainer-cache
mkdir -p "$APPTAINER_CACHEDIR"
apptainer build dev.sif apptainer/dev.def
```

## "Port forwarding to a running job disconnects"

SSH keepalive on most systems is loose. Add to `~/.ssh/config`:

```
Host alvis
  ServerAliveInterval 60
  ServerAliveCountMax 10
```

If the forwarded port refuses connections, check:

- Is the job actually running? `squeue -u $USER`
- Did the server come up? Look at the job's `.out` file.
- Is the port correct? Re-read `$RESULTS_DIR/<server>-port.txt`.
- Is the compute node name correct? Re-read `<server>-host.txt`.

## "My .env keys leaked somewhere"

First: don't panic; rotate them immediately at the provider.

Then: figure out how they leaked.

```bash
# Search committed history for common key shapes
git log -p | grep -E '(sk-[a-zA-Z0-9]{40}|hf_[a-zA-Z0-9]{20}|ghp_[a-zA-Z0-9]{36})'

# Search working tree
grep -rE 'sk-[a-zA-Z0-9]{40}|hf_[a-zA-Z0-9]{20}|ghp_[a-zA-Z0-9]{36}' .
```

If the key is in committed history, rewriting the history with
`git-filter-repo` is a separate (careful) conversation.

## "Mimer filled up"

Check usage in the NAISS portal. Unlike Cephyr there's no sudden
hard cap in most cases, but it can eventually fail writes. Clean up
in this order:

1. Old `wandb/` run directories — move to laptop, delete remote.
2. Superseded `checkpoints/` — keep the final, drop intermediates.
3. `hf-cache/` for models you no longer use.
4. Old SIFs under `sifs/` — you can rebuild from `.def`.

Ask C3SE for an allocation increase only after cleaning up — support
will ask about your housekeeping first.
