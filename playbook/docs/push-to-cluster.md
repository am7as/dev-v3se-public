# Push: code to Cephyr, data to Mimer

Two destinations, two scripts, one transport host:
**`alvis2.c3se.chalmers.se`** by default (works for everyone with
Alvis access). If you have a Vera project,
`vera2.c3se.chalmers.se` is faster for bulk transfers — set
`CEPHYR_TRANSFER_HOST=vera2.c3se.chalmers.se` in your `.env` (or
swap `HostName` in the `cephyr-transfer` SSH alias). Same paths,
same scripts, just a different door. See
[transfer-methods.md](transfer-methods.md#which-transfer-host-alvis-vs-vera).

## Pushing code (Cephyr)

Every project template ships `_shared/scripts/sync-to-cephyr.sh`.
Run it from the project root after editing code:

**PowerShell (Windows):**

```powershell
bash .\_shared\scripts\sync-to-cephyr.sh            # uses .env for credentials
bash .\_shared\scripts\sync-to-cephyr.sh --dry-run  # preview only
```

**bash / zsh (macOS / Linux):**

```bash
bash ./_shared/scripts/sync-to-cephyr.sh
bash ./_shared/scripts/sync-to-cephyr.sh --dry-run
```

What the script does:

- Reads `CEPHYR_USER` and `CEPHYR_PROJECT_DIR` from `.env`.
- `rsync -avh` your project root → `<user>@alvis2.c3se.chalmers.se:<cephyr-path>/`.
- **Excludes** `.pixi/`, `.venv/`, `__pycache__/`, `.hf-cache/`,
  `results/`, `*.sif`, `.git/`, `.env`, `slurm-*.out`, `slurm-*.err`.

### Manual equivalent (both platforms)

```bash
rsync -avh --progress --delete \
  --exclude='.pixi/' --exclude='__pycache__/' --exclude='.venv/' \
  --exclude='.hf-cache/' --exclude='results/' --exclude='*.sif' \
  --exclude='.git/' --exclude='.env' \
  --exclude='slurm-*.out' --exclude='slurm-*.err' \
  ./  <cid>@alvis2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/<project>/
```

## Pushing data / weights (Mimer)

Every project template ships `_shared/scripts/sync-to-mimer.sh` (once
`.env` has `MIMER_GROUP_ROOT` set). Use for anything big that needs
to end up under your project's Mimer allocation.

**PowerShell:**

```powershell
# Push ./data → $MIMER_GROUP_ROOT/data/
bash .\_shared\scripts\sync-to-mimer.sh .\data

# Push ./models → $MIMER_GROUP_ROOT/models/llama-8b/
bash .\_shared\scripts\sync-to-mimer.sh .\models models/llama-8b

# Dry run
bash .\_shared\scripts\sync-to-mimer.sh --dry-run .\data
```

**bash / zsh:**

```bash
bash ./_shared/scripts/sync-to-mimer.sh ./data
bash ./_shared/scripts/sync-to-mimer.sh ./models models/llama-8b
bash ./_shared/scripts/sync-to-mimer.sh --dry-run ./data
```

What the script does:

- Reads `CEPHYR_USER` (for the SSH login) and `MIMER_GROUP_ROOT`
  from `.env`.
- `rsync -avh` the local directory → `<user>@alvis2.c3se.chalmers.se:<mimer-path>/<subdir>/`.
- Minimal exclusions (only `.DS_Store`, `Thumbs.db`, `*.pyc`,
  `__pycache__/`) — unlike the Cephyr sync, you probably want your
  data as-is.

### Manual equivalent

```bash
rsync -avh --progress \
  ./my-data/  <cid>@alvis2.c3se.chalmers.se:/mimer/NOBACKUP/groups/<naiss-id>/my-data/
```

## Very-large transfers (> 100 GB)

Avoid rsync-over-SSH for multi-hundred-GB data. C3SE documents
bulk-transfer options (Globus, Aspera); see
<https://www.c3se.chalmers.se/documentation/file_transfer/bulk_data_transfer/>.

## Keeping things fresh on cluster

After each push:

```bash
ssh alvis
cd /cephyr/users/<cid>/Alvis/<project>
# Optionally rebuild the SIF if deps changed:
apptainer build -F dev.sif apptainer/dev.def
```

For a tight edit-submit loop, pair `sync-to-cephyr.sh` with a quick
`sbatch slurm/gpu-t4.sbatch` — the template's helper scripts keep
this a one-liner.
