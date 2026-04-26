# Usage — `13-train-infer-pipeline` (step-by-step, zero to results)

A complete walkthrough from an empty folder to a **three-phase
pipeline**:

1. **Train** — LoRA finetune a base HF model on a tiny text dataset.
   Checkpoints and the final adapter land on Mimer (not Cephyr).
2. **Bundle** — `scripts/bundle.py` materializes
   `apptainer/bundle.def.tpl` with the real adapter path and base-model
   id, then `apptainer build`s a portable SIF that embeds the adapter at
   `/opt/adapter` and pins `HF_MODEL` at build time.
3. **Infer** — run the bundled SIF. No `--adapter-dir` needed; the SIF
   auto-loads its own adapter.

Each phase is a separate `pixi` task **and** a separate sbatch. This
example composes `05-train-lora` with a build-time packaging step.

## 1. What you'll end up with

- A LoRA adapter (few MB) under
  `$RESULTS_DIR/adapters/<timestamp>/`.
- A `<timestamp>.sif` (2–5 GB depending on base model) under
  `$RESULTS_DIR/bundles/`, plus a `.def` and a `.json` manifest.
- Generated text from `apptainer run --nv <bundle>.sif --prompt "..."`,
  with zero host-side HF dependencies beyond Apptainer itself.

## 2. Prerequisites

**On laptop**:

- Docker Desktop or Docker Engine.
- `git`.
- For the bundle phase: Apptainer (WSL2 on Windows, native on Linux,
  or skip locally and only bundle on Alvis — on macOS this is the only
  option).

**On cluster**:

- C3SE account with Alvis allocation (NAISS project ID).
- SSH to `alvis1.c3se.chalmers.se` / `alvis2.c3se.chalmers.se`.
- Train phase uses `T4:1`; bundle phase is CPU-only; inference phase
  uses `T4:1`. Adjust upward in the sbatch files if your base model
  needs more.
- HuggingFace token (`HF_TOKEN`) if your base model is gated.

## 3. Clone the template

**PowerShell:**

```powershell
Copy-Item . ..\my-train-infer -Recurse
cd ..\my-train-infer
```

**bash / zsh:**

```bash
cp -r . ../my-train-infer
cd ../my-train-infer
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
CEPHYR_PROJECT_PATH=/cephyr/users/<cid>/Alvis/my-train-infer
MIMER_GROUP_PATH=/mimer/NOBACKUP/groups/<naiss-id>
MIMER_PROJECT_PATH=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-train-infer

# Base model (tiny default for the laptop loop; swap for real runs).
HF_MODEL=sshleifer/tiny-gpt2
# Optional: pin a snapshot from the shared Mimer HF mirror.
# HF_MODEL_SNAPSHOT=/mimer/NOBACKUP/Datasets/LLM/huggingface/hub/models--<org>--<name>/snapshots/<hash>/
HF_HOME=/workspace/.hf-cache
TRANSFORMERS_CACHE=/workspace/.hf-cache
HF_TOKEN=                             # for gated models

HF_DATASET=                           # empty = built-in 5-row toy set
LORA_R=8
LORA_ALPHA=16
LORA_DROPOUT=0.05
NUM_EPOCHS=1
BATCH_SIZE=4
LEARNING_RATE=1e-4

# Optional experiment tracking
WANDB_API_KEY=
WANDB_PROJECT=v3se-train-infer
WANDB_MODE=offline
MLFLOW_TRACKING_URI=
MLFLOW_EXPERIMENT=v3se-train-infer
```

Patch the Slurm `--account` in **all three** `slurm/*.sbatch`:

```diff
-#SBATCH --account=<PROJECT_ID>
+#SBATCH --account=<naiss-id>
```

## 5. Laptop smoke test (Docker + pixi)

```bash
docker compose up -d dev
docker compose exec dev pixi install
docker compose exec dev pixi run smoke
```

`smoke` prints torch / transformers / peft / trl versions and a
`cuda_available` flag (`false` on most laptops; that's fine for the
toy dataset). Then do a real training run — **tiny-gpt2 + 5 rows
finishes in under a minute on CPU**:

```bash
docker compose exec dev pixi run train
```

Look for the line `Adapter: /results/adapters/<ts>` at the end. That
directory is what phase 2 packages.

Optional quick inference against the raw adapter (no bundle yet):

```bash
docker compose exec dev pixi run infer \
    --adapter-dir /results/adapters/<ts> \
    --prompt "Chalmers is"
```

## 6. Build / bake step (the bundle phase, on laptop)

If you have Apptainer locally you can run phase 2 on the laptop too —
otherwise skip this section and run bundling on Alvis (step 10b).

```bash
docker compose exec dev apptainer --version   # confirm availability
docker compose exec dev pixi run bundle --adapter-dir /results/adapters/<ts>
# → results/bundles/<ts>.sif
# → results/bundles/<ts>.def        (materialized from bundle.def.tpl)
# → results/bundles/<ts>.json       (manifest: sif, def, adapter_dir, base_model)
```

The bundler substitutes two tokens in `apptainer/bundle.def.tpl`:

- `ADAPTER_SRC` → the adapter directory (baked into `/opt/adapter`)
- `BASE_MODEL` → `HF_MODEL` from `.env` (or `--base-model`
  override); baked into the SIF's `%environment`

Test the bundled SIF directly:

```bash
docker compose exec dev apptainer run results/bundles/<ts>.sif --prompt "Alvis is"
# (no --nv since this is CPU on the laptop)
```

Separately, there are **two other Apptainer defs** in this example:

- `apptainer/dev.def` — plain Pixi base; used by `train-t4.sbatch` and
  `bundle.sbatch` as the "builder" SIF.
- `apptainer/app.def` — alternative frozen SIF with code baked in
  (rarely needed; the bundle supersedes it for deploy).

Neither needs building on the laptop if you only do phase 1 locally.

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
git clone git@github.com:<team>/<project>.git my-train-infer
cd my-train-infer
```

Copy `.env`:

**PowerShell:**

```powershell
scp .env <cid>@alvis2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/my-train-infer/.env
```

**bash / zsh:**

```bash
scp .env <cid>@alvis2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/my-train-infer/.env
```

### 7b. rsync fallback

```bash
bash _shared/scripts/sync-to-cephyr.sh
```

Excludes `results/`, `*.sif`, `.pixi/` — none of which belong on
Cephyr anyway.

### 7c. Move heavy training outputs to Mimer

The per-job sbatch files default to `RESULTS_DIR=$PWD/results` which
is **on Cephyr** — fine for the toy dataset, unacceptable for real
training. Point results at Mimer by either:

- Editing each sbatch's `export RESULTS_DIR=...` line to
  `export RESULTS_DIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-train-infer/results`, **or**
- Symlinking `ln -s /mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-train-infer/results ./results`
  inside the project once.

Adapters and `.sif` bundles are exactly the kind of thing Cephyr's
quota was **not** designed for.

## 8. Cluster setup

```bash
ssh <cid>@alvis2.c3se.chalmers.se
cd /cephyr/users/<cid>/Alvis/my-train-infer

export APPTAINER_CACHEDIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/apptainer-cache
mkdir -p "$APPTAINER_CACHEDIR"

apptainer build dev.sif apptainer/dev.def
```

`dev.sif` is the builder used by both the train and bundle phases.
The bundled SIFs in phase 2 are built *inside* this SIF's
`apptainer build` call.

## 9. Cluster smoke

There's no standalone cpu-smoke sbatch in this example; the train
phase on tiny-gpt2 **is** the smoke:

```bash
sbatch slurm/train-t4.sbatch
squeue -u $USER
cat slurm-train-infer-train-*.out
```

Expect ~1 min wall time with the default tiny-gpt2 + built-in toy
dataset. Grep the log for `Adapter: <path>` — note the full path
(inside a SIF it'll look like `/workspace/results/adapters/<ts>`
→ on host, the sbatch's `RESULTS_DIR`).

## 10. Run real workload (three phases)

### 10a. Phase 1 — Train

Flip `.env` to your real base model + dataset:

```ini
HF_MODEL=meta-llama/Llama-3.2-1B-Instruct
# Or a pinned snapshot from the shared Mimer HF mirror:
# HF_MODEL_SNAPSHOT=/mimer/NOBACKUP/Datasets/LLM/huggingface/hub/models--meta-llama--Llama-3.2-1B-Instruct/snapshots/<hash>/
HF_DATASET=tatsu-lab/alpaca
NUM_EPOCHS=3
BATCH_SIZE=8
```

For a 1–7B model on T4 the default sbatch should be enough; for bigger
or multi-GPU jump to `21-distributed-finetune`.

```bash
sbatch slurm/train-t4.sbatch
# ... after Slurm says CG ...
cat slurm-train-infer-train-*.out | grep Adapter
# Adapter: /mimer/.../results/adapters/<ts>
```

Capture that path — phases 2 and 3 both need it.

### 10b. Phase 2 — Bundle

`bundle.sbatch` expects the adapter path via `--export`:

```bash
sbatch --export=ALL,ADAPTER=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-train-infer/results/adapters/<ts> \
       slurm/bundle.sbatch
```

Inside, `apptainer build` materializes `bundle.def.tpl`:

- reads `$ADAPTER` → substitutes `ADAPTER_SRC`
- reads `HF_MODEL` from `.env` → substitutes `BASE_MODEL`
- `%files: ADAPTER_SRC /opt/adapter` copies the adapter **into** the SIF
- `%environment: BUNDLED_ADAPTER_DIR=/opt/adapter` is exported
- `%runscript` is `pixi run infer --adapter-dir
  "$BUNDLED_ADAPTER_DIR" "$@"` — so the SIF auto-infers

Output:

```
$RESULTS_DIR/bundles/<ts>.sif    ← the portable file
$RESULTS_DIR/bundles/<ts>.def    ← materialized recipe (auditable)
$RESULTS_DIR/bundles/<ts>.json   ← manifest
```

The bundle phase runs `apptainer build` **inside** `dev.sif`. Alvis's
compute nodes support fakeroot/user-namespaces for this — no
privileged access required.

### 10c. Phase 3 — Infer

```bash
sbatch --export=ALL,BUNDLE=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-train-infer/results/bundles/<ts>.sif,PROMPT="Alvis is" \
       slurm/infer.sbatch
```

`infer.sbatch` runs `apptainer run --nv "$BUNDLE" --prompt "$PROMPT"`
— no `dev.sif`, no binds, no adapter path. Everything needed is baked
into `<ts>.sif`, which is the whole point of the bundle.

Ship `<ts>.sif` to a collaborator and they reproduce your inference
byte-for-byte: `apptainer run --nv <ts>.sif --prompt "..."`.

### Optional — experiment tracking

Fill in `.env` before phase 1:

```ini
WANDB_API_KEY=<key>
WANDB_PROJECT=v3se-train-infer
WANDB_MODE=online          # offline if compute nodes lack outbound

# or MLflow:
MLFLOW_TRACKING_URI=http://<your-mlflow>:5000
MLFLOW_EXPERIMENT=v3se-train-infer
```

The Trainer picks these up automatically via
`TrainingArguments(report_to=_report_to())` in `src/train_infer/train.py`.
No code change.

## 11. Retrieve results

**PowerShell:**

```powershell
rsync -avh --progress `
  <cid>@alvis2.c3se.chalmers.se:/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-train-infer/results/ `
  .\results\
```

**bash / zsh:**

```bash
rsync -avh --progress \
  <cid>@alvis2.c3se.chalmers.se:/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-train-infer/results/ \
  ./results/
```

Or, if you left `RESULTS_DIR=$PWD/results` on Cephyr:

```bash
bash _shared/scripts/sync-from-cephyr.sh
```

Key things to fetch:

- `results/adapters/<ts>/` — the raw adapter (tiny, fine to keep on
  laptop).
- `results/bundles/<ts>.json` — the manifest; always pull this.
- `results/bundles/<ts>.sif` — **big**; pull only if you need to run
  inference on the laptop or hand to a collaborator.

## 12. Verification checklist

- [ ] `.env` has real `HF_MODEL` and (if gated) `HF_TOKEN`.
- [ ] All three `slurm/*.sbatch` have your real `--account=<naiss-id>`.
- [ ] `RESULTS_DIR` points at Mimer (not Cephyr) for non-toy training.
- [ ] `APPTAINER_CACHEDIR` points at Mimer.
- [ ] Phase 1: `results/adapters/<ts>/adapter_model.safetensors` exists
      and `run_summary.json` shows non-zero `trainable_params`.
- [ ] Phase 2: `results/bundles/<ts>.sif` + `.def` + `.json` all exist.
      The `.def` file has the real adapter path substituted for
      `ADAPTER_SRC` and the real model id for `BASE_MODEL`.
- [ ] Phase 3: `slurm-train-infer-infer-*.out` contains generated
      text, not just the prompt.
- [ ] `apptainer run --nv <ts>.sif --prompt "hi"` works on a fresh
      machine with only Apptainer installed.

## 13. Troubleshooting

- **Phase 1 OOM on T4 with a real model** → default `BATCH_SIZE=4` is
  too big for some 7B models on T4. Drop to `BATCH_SIZE=1`, or use
  gradient accumulation, or move to `21-distributed-finetune`.

- **`bundle.py` fails "Bundle template not found"** → the bundler
  looks for `apptainer/bundle.def.tpl` two levels up from
  `src/train_infer/bundler.py`. If you renamed the project dir
  layout, pass `tpl_path=` explicitly or restore the original path.

- **`apptainer build` in phase 2 exits with "fakeroot not
  supported"** → you're on a node that lacks user-namespaces. Build
  on the login node (`alvis1`/`alvis2`) instead of compute by just
  running `apptainer build` interactively, or flag the bundle
  sbatch with `#SBATCH --partition=alvis` (already set) + a node
  that supports fakeroot (most do).

- **Phase 3 SIF prints only the prompt, no generated text** → the
  adapter didn't actually load. Confirm by running
  `apptainer exec --nv <ts>.sif ls /opt/adapter` — you should see
  `adapter_config.json` + `adapter_model.safetensors`. If the
  directory is empty, the `%files` substitution in the materialized
  `.def` didn't work — check the `.json` manifest's `adapter_dir`
  points at a real directory and rerun phase 2.

- **Base-model download from HF fails on compute node** → gated or
  rate-limited. Pre-download to the shared Mimer mirror
  (`/mimer/NOBACKUP/Datasets/LLM/huggingface/hub/`) or set
  `HF_MODEL_SNAPSHOT` to an already-mirrored path, then rerun phase 1.
  The base model is fetched **at bundle-build time** too — make sure
  `HF_TOKEN` is exported in `bundle.sbatch` if needed.

- **`<ts>.sif` is suspiciously small (< 200 MB)** → the base-model
  weights weren't pulled into the SIF. Check
  `bundle.def.tpl`'s `%post` section; the version shipped with this
  template doesn't pre-download weights (the SIF pulls them at first
  run). If you want fully-offline bundles, extend `%post` to
  `python -c "from transformers import AutoModel;
  AutoModel.from_pretrained('BASE_MODEL')"` — but note this can
  double SIF size.
