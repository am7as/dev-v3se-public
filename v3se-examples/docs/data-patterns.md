# Data patterns — where your data lives and how to get at it

Every template reads data from `$DATA_DIR` (= `/data` inside the
container). The interesting question is **what the host side is**. Pick
the pattern that matches your situation.

## Pattern 1 — Local disk (laptop only)

Default layout. `data/` is a sibling of the project:

```
my-project/          ← repo
../data/             ← host path
```

In `.env`, leave `DATA_HOST` blank. The sibling default kicks in.

## Pattern 2 — External hard drive

```ini
# .env
DATA_HOST=E:/big-dataset
```

Windows: Docker Desktop → Settings → Resources → File sharing → add
`E:\`. Then `docker compose down && up -d`.

## Pattern 3 — Cephyr private (your cluster home)

Cephyr is small (30 GiB / 60k files). Reasonable for code, configs,
and tiny datasets you want versioned alongside your code. Big data
goes on Mimer (Pattern 4):

```bash
apptainer run --nv \
    --bind /cephyr/users/$USER/Alvis/my-project/sample-data:/data \
    dev.sif pixi run infer
```

**Don't** dump model weights, large datasets, or checkpoint trees
here. That's what Mimer is for (Pattern 4).

## Pattern 4 — Mimer project storage (large, writable, per-project)

Your project has a Mimer allocation at
`/mimer/NOBACKUP/groups/<naiss-id>/` (e.g. `/mimer/NOBACKUP/groups/naiss2025-22-321/`).
Typical size is **hundreds of GiB** — this is where big things go.

```bash
apptainer run --nv \
    --bind /mimer/NOBACKUP/groups/naiss2025-22-321/my-dataset:/data \
    --bind /mimer/NOBACKUP/groups/naiss2025-22-321/$USER/results:/results \
    --bind /mimer/NOBACKUP/groups/naiss2025-22-321/$USER/models:/models \
    dev.sif pixi run train
```

Recommended sub-layout under the project's Mimer root:

```
/mimer/NOBACKUP/groups/<naiss-id>/
├── shared/               # team-shared datasets, read-write
├── models/               # trained weights, sharable
└── <cid>/                # your personal scratch under the project
    ├── results/
    ├── checkpoints/
    ├── wandb/
    └── mlruns/
```

**No backups on Mimer** — keep irreplaceable originals somewhere safe.

## Pattern 5 — Shared read-only datasets (C3SE-provided)

C3SE pre-provisions common datasets at `/mimer/NOBACKUP/Datasets/`.
Read-only, doesn't count against your quota:

- `/mimer/NOBACKUP/Datasets/nuScenes/`
- `/mimer/NOBACKUP/Datasets/LLM/huggingface/hub/`
- `/mimer/NOBACKUP/Datasets/ImageNet/`

```bash
apptainer run --nv \
    --bind /mimer/NOBACKUP/Datasets/nuScenes:/data:ro \
    dev.sif pixi run preprocess
```

The `:ro` is belt-and-suspenders — Apptainer can't write to
`/mimer/NOBACKUP/Datasets/` anyway.

## Pattern 6 — HuggingFace Hub (three flavours)

**6a. Pre-downloaded on C3SE (preferred for any model C3SE already mirrors):**

```ini
# .env on Alvis
HF_MODEL_SNAPSHOT=/mimer/NOBACKUP/Datasets/LLM/huggingface/hub/models--meta-llama--Llama-3.1-8B/snapshots/<hash>/
```

No download, no quota hit, instant load.

**6b. Clone once and bundle into a SIF:**

Use the helper that bakes weights into a `.sif` at build time:

```bash
bash _shared/scripts/fetch-hf-model.sh meta-llama/Llama-3.1-8B ./models/llama3-8b.sif
```

One file on Cephyr, no quota explosion.

**6c. Direct streaming (cache-at-call):**

```ini
# .env — cache MUST NOT default to $HOME on Alvis
HF_HOME=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/.hf-cache
```

Works, but every job re-downloads if the cache is cold. Prefer 6a
when C3SE mirrors the model; prefer 6b for models you'll call many
times.

## Pattern 7 — Google Cloud Storage / S3 / Azure Blob

Docker/Apptainer can't bind-mount cloud buckets directly. Two options:

**A. Pre-sync with `rclone` or `gsutil`** — target Mimer:
```bash
gsutil -m rsync -r gs://waymo-public/v1 /mimer/NOBACKUP/groups/<naiss-id>/waymo-data
```
Then use Pattern 4.

**B. FUSE-mount on the host**:
```bash
rclone mount waymo:v1 /mnt/waymo &
# Then DATA_HOST=/mnt/waymo (laptop) or bind /mnt/waymo:/data (Alvis)
```

## Pattern 8 — HuggingFace Datasets

```python
from datasets import load_dataset
ds = load_dataset("nvidia/PhysicalAI-Autonomous-Vehicles",
                  cache_dir=os.environ.get("HF_HOME"))
```

Same `HF_HOME` rules apply — never let it default to `$HOME` or
Cephyr on Alvis. Point at Mimer.

## Mixing patterns per run

Bind multiple sources at once:

```bash
apptainer run --nv \
    --bind /mimer/NOBACKUP/Datasets/nuScenes:/data/nuscenes:ro \
    --bind /mimer/NOBACKUP/groups/<naiss-id>/$USER/annotations:/data/annotations \
    dev.sif pixi run train
```

Your code sees `/data/nuscenes` (read-only, C3SE-shared) and
`/data/annotations` (writable, your Mimer allocation). Common pattern
for training-on-shared, writing-metadata-to-yours.

## Which templates demonstrate which pattern

| Template                     | Pattern(s) shown                                                  |
|------------------------------|-------------------------------------------------------------------|
| `01-foundation`              | 1 (local sibling)                                                 |
| `03-hf-shared-hub`           | 6a (HF from C3SE shared hub)                                      |
| `04-data-cephyr`             | 1, 3, 4, 5 (local → Cephyr private / Mimer / shared read-only)    |
| `08-hf-sif-bundle`           | 6b (HF cloned + baked into SIF)                                   |
| `09-hf-hub-streaming`        | 6c (HF streamed from Hub)                                         |
| `12-multi-source-data`       | **all** of them, switchable by config key                         |
| `14-git-model-bundle`        | Model weights from a git repo → SIF (cluster) or Docker (laptop)  |
