# Usage — `12-multi-source-data` (step-by-step, zero to results)

A complete walkthrough from an empty folder to a data-processing
pipeline where the same code reads from any of six sources, picked by
config:

1. **local** — files under the container's `/data` (a sibling of the
   repo on the host).
2. **cephyr_private** — your own `/cephyr/users/<cid>/...` directory,
   bound into `/data` at sbatch time.
3. **mimer_shared** — read-only `/mimer/NOBACKUP/Datasets/...`
   (nuScenes, ImageNet, and friends).
4. **hf_hub** — a HuggingFace Datasets Hub id, cached under `HF_HOME`.
5. **gcs** — a Google Cloud Storage bucket via `rclone`.
6. Plus any extras you add under `src/data_multi/sources/`.

The routing knob is `configs/sources.yaml` + the `DATASET_SOURCE` env
var (overridable with `--source`). The per-environment **bind mapping**
lives in the sbatch files — code stays source-agnostic.

## 1. What you'll end up with

- Laptop dev loop: `pixi run process --source local|hf_hub` iterates
  shipped sample data or a HuggingFace dataset.
- On Alvis: three dedicated sbatch files (`process-local.sbatch`,
  `process-mimer-shared.sbatch`, `process-private.sbatch`) that bind the
  right storage into `/data` and call the same script.
- Summary JSON at `$RESULTS_DIR/summary.json`.

## 2. Prerequisites

**On laptop**:

- Docker Desktop or Docker Engine.
- `git`.
- Optional: `rclone` configured on the host if you want to test the
  `gcs` source locally.

**On cluster**:

- C3SE account with Alvis allocation (NAISS project ID).
- SSH to `alvis1.c3se.chalmers.se` / `alvis2.c3se.chalmers.se`.
- For `mimer_shared`: the dataset you want exists under
  `/mimer/NOBACKUP/Datasets/`. Check with
  `ls /mimer/NOBACKUP/Datasets/` first.
- For `cephyr_private`: your data already lives on Cephyr (code) or
  Mimer (weights / large data). Use
  `bash _shared/scripts/sync-to-mimer.sh <local-dir>` to push if not.

## 3. Clone the template

**PowerShell:**

```powershell
Copy-Item . ..\my-data-multi -Recurse
cd ..\my-data-multi
```

**bash / zsh:**

```bash
cp -r . ../my-data-multi
cd ../my-data-multi
```

## 4. Configure `.env`

**PowerShell:**

```powershell
Copy-Item .env.example .env
```

**bash / zsh:**

```bash
cp .env.example .env
```

Edit `.env`:

```ini
CEPHYR_USER=<cid>
CEPHYR_PROJECT_PATH=/cephyr/users/<cid>/Alvis/my-data-multi
MIMER_GROUP_PATH=/mimer/NOBACKUP/groups/<naiss-id>
MIMER_PROJECT_PATH=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-data-multi

# Which source to read from when --source is omitted.
DATASET_SOURCE=local

# HuggingFace cache — must NOT land in $HOME on Alvis (quota).
HF_HOME=/workspace/.hf-cache
TRANSFORMERS_CACHE=/workspace/.hf-cache
HF_TOKEN=                 # only for gated datasets

# rclone remote — only used when DATASET_SOURCE=gcs.
GCS_RCLONE_REMOTE=waymo
GCS_RCLONE_PATH=open/v1
```

Patch the Slurm `--account` in **all three** `slurm/*.sbatch` files:

```diff
-#SBATCH --account=<PROJECT_ID>
+#SBATCH --account=<naiss-id>
```

### Optional — register real datasets under `configs/sources.yaml`

The shipped file registers a few examples per source:

```yaml
mimer_shared:
  examples:
    nuScenes: "/mimer/NOBACKUP/Datasets/nuScenes"
    imagenet: "/mimer/NOBACKUP/Datasets/ImageNet"

hf_hub:
  examples:
    imdb:   "imdb"
    alpaca: "tatsu-lab/alpaca"
```

Add your own logical name → path pairs here so teammates have a single
place to look up "what does `mimer_shared.waymo_v2` point at?".

### Optional — host-side data for `local`

The shipped `data/sample/` contains a tiny CSV used by the smoke test.
If your laptop has real data elsewhere, override the bind via
`DATA_HOST` in `.env`:

```ini
DATA_HOST=/c/users/<you>/datasets
# or on macOS/Linux:
# DATA_HOST=/Users/<you>/datasets
```

## 5. Laptop smoke test (Docker + pixi)

```bash
docker compose up -d dev
docker compose exec dev pixi install
docker compose exec dev pixi run smoke
```

Expect JSON like:

```
{
  "template": "data-multi",
  "current_source": "local",
  "available": ["cephyr_private","mimer_shared","gcs","hf_hub","local"],
  ...
}
```

Then exercise two sources end-to-end — **this is your sanity check that
the routing works**:

```bash
# Flow A — local (files under ./data/sample)
docker compose exec dev pixi run process --source local --dataset sample

# Flow B — HuggingFace dataset (streams into HF_HOME)
docker compose exec dev pixi run process --source hf_hub --dataset-id imdb --split train
```

Both produce `results/summary.json`. Inspect it:

- For `local`, you should see `file_count`, `total_rows`, and per-file
  row/column counts.
- For `hf_hub`, you should see `rows`, `columns`, and a sample example
  row.

### Optional — GCS on laptop

1. On **host**: `rclone config` once — create a remote of type
   `google cloud storage` named (e.g.) `waymo`.
2. Open `docker-compose.yml` and add a volume:

   ```yaml
   volumes:
     # ...
     - ~/.config/rclone:/root/.config/rclone:ro
   ```

3. `docker compose exec dev pixi run process --source gcs`.

## 6. Build / bake step

Two Apptainer defs ship here:

- `apptainer/dev.def` — interactive SIF, includes `rclone` for the GCS
  source.
- `apptainer/app.def` — frozen SIF (bakes code), also with `rclone`.

Skip locally; build on Alvis in step 8.

## 7. Push to cluster (git preferred, rsync fallback)

### 7a. Git

```bash
git init -b main
git add .
git commit -m "initial scaffold"
git remote add origin git@github.com:<team>/<project>.git
git push -u origin main
```

On Alvis:

```bash
ssh <cid>@alvis2.c3se.chalmers.se
mkdir -p /cephyr/users/<cid>/Alvis
cd /cephyr/users/<cid>/Alvis
git clone git@github.com:<team>/<project>.git my-data-multi
cd my-data-multi
```

Copy `.env` separately:

**PowerShell:**

```powershell
scp .env <cid>@alvis2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/my-data-multi/.env
```

**bash / zsh:**

```bash
scp .env <cid>@alvis2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/my-data-multi/.env
```

### 7b. rsync fallback

```bash
bash _shared/scripts/sync-to-cephyr.sh
```

### 7c. Push private data to Mimer (if using `cephyr_private`)

Cephyr is for **code** only; put data on Mimer:

**PowerShell:**

```powershell
bash _shared/scripts/sync-to-mimer.sh .\data\my-dataset my-data-multi/data
```

**bash / zsh:**

```bash
bash _shared/scripts/sync-to-mimer.sh ./data/my-dataset my-data-multi/data
```

This writes to `$MIMER_GROUP_PATH/my-data-multi/data/`. You'll bind
that into `/data` at sbatch time (step 10).

## 8. Cluster setup

```bash
ssh <cid>@alvis2.c3se.chalmers.se
cd /cephyr/users/<cid>/Alvis/my-data-multi

export APPTAINER_CACHEDIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/apptainer-cache
mkdir -p "$APPTAINER_CACHEDIR"

apptainer build dev.sif apptainer/dev.def
```

## 9. Cluster smoke

The three sbatch files all run the same `process` task — the smoke is
whichever source is cheapest to check (local sample shipped with the
repo):

```bash
sbatch slurm/process-local.sbatch
squeue -u $USER
cat slurm-data-multi-local-*.out
```

Expect `source : local`, `reading: /data/sample`, and a `summary:`
line with counts.

There is no GPU job in this example — all three sbatch files request
CPU + RAM only.

## 10. Run real workload

### Flow A — `local` (dev-friendly)

Use this on the laptop with the shipped sample, or on Alvis when you've
put small inputs inside the repo.

```bash
sbatch slurm/process-local.sbatch
# uses: --source local --dataset sample
```

### Flow B — `mimer_shared` (read-only `/mimer/NOBACKUP/Datasets/...`)

Edit `slurm/process-mimer-shared.sbatch` to bind the dataset you want, or
pass via `--export`:

```bash
sbatch --export=ALL,SHARED_PATH=/mimer/NOBACKUP/Datasets/nuScenes \
       slurm/process-mimer-shared.sbatch
```

The sbatch binds `$SHARED_PATH:/data:ro` — the `:ro` is deliberate.
Shared datasets are read-only by convention; if your code ever tries
to write into `/data`, switch to `cephyr_private`.

### Flow C — `cephyr_private` (your own group path on Mimer)

```bash
sbatch --export=ALL,PRIVATE_PATH=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-data-multi/data \
       slurm/process-private.sbatch
```

(Despite the name `cephyr_private`, data on Mimer is preferred —
Cephyr is reserved for code. The source name is historical.)

### Flow D — `hf_hub` on Alvis

No dedicated sbatch; reuse `process-local.sbatch` with the env flipped:

```bash
sbatch --export=ALL,DATASET_SOURCE=hf_hub,DATASET_ID=imdb slurm/process-local.sbatch
```

Then edit the `apptainer run` line at the bottom of that sbatch to
pass `--source hf_hub --dataset-id $DATASET_ID` instead of the
local defaults. `HF_HOME` is already pointed at `$PWD/.hf-cache` so
the dataset lands next to your project, not in `$HOME`.

## 11. Retrieve results

**PowerShell:**

```powershell
rsync -avh --progress `
  <cid>@alvis2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/my-data-multi/results/ `
  .\results\
```

**bash / zsh:**

```bash
rsync -avh --progress \
  <cid>@alvis2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/my-data-multi/results/ \
  ./results/
```

Or:

```bash
bash _shared/scripts/sync-from-cephyr.sh
```

Open `results/summary.json` — the `source` field tells you which
backend produced it.

## 12. Verification checklist

- [ ] `.env` has `DATASET_SOURCE` set and any source-specific vars
      (`HF_TOKEN` for gated HF datasets, `GCS_RCLONE_*` for GCS).
- [ ] All three `slurm/*.sbatch` have your real `--account=<naiss-id>`.
- [ ] `APPTAINER_CACHEDIR` is under Mimer, not `$HOME`.
- [ ] Laptop smoke: `pixi run process --source local` produces
      `results/summary.json` with `source: "local"`.
- [ ] Laptop smoke: `pixi run process --source hf_hub --dataset-id
      imdb` produces `results/summary.json` with `source: "hf_hub"`
      and non-empty `example`.
- [ ] Cluster smoke: `process-local.sbatch` completes with exit 0 and
      shows the same `source: "local"` summary in `results/`.
- [ ] `C3SE_quota` on Alvis shows no surprise usage on `$HOME`
      (the HF cache should have gone to `$PWD/.hf-cache`).

## 13. Troubleshooting

- **"No CSVs under /data"** when using `local` → the bind points at
  the wrong host dir. Check `DATA_HOST` in `.env` (laptop) or the
  `--bind` in the sbatch (cluster). `docker compose exec dev ls /data`
  and `apptainer exec --bind ... dev.sif ls /data` are fast checks.

- **HF dataset download blows through quota** → `HF_HOME` defaulted to
  `$HOME`. Make sure `.env` sets it to `/workspace/.hf-cache` (laptop)
  and that each sbatch exports `HF_HOME=$PWD/.hf-cache` before
  `apptainer run`. `cpu.sbatch` in `_shared/slurm/` does this correctly
  — use it as a template if you edit the per-example sbatch files.

- **"Permission denied" writing to `/data`** when using
  `mimer_shared` → you tried to write into a read-only bind. Keep
  outputs in `$RESULTS_DIR`; never under `/data` when bound `:ro`.

- **GCS source fails "no such remote"** → `rclone.conf` isn't bound
  into the SIF. On laptop: add the volume in `docker-compose.yml`.
  On Alvis: `mkdir -p ~/.config/rclone && rclone config` on the login
  node, then add `--bind ~/.config/rclone:/root/.config/rclone:ro`
  to the apptainer run line.

- **`imdb` HF dataset gated or rate-limited** → set `HF_TOKEN` in
  `.env` (and export it inside the sbatch) if the dataset requires
  auth; otherwise try a public one like `squad` to narrow down the
  failure.

- **`mimer_shared` dataset not visible** → the dataset may have been
  renamed / moved by C3SE admins. `ls /mimer/NOBACKUP/Datasets/` to
  list the current names, then update the path in
  `configs/sources.yaml` or the sbatch `--export`.
