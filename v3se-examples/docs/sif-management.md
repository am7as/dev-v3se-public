# SIF management — living inside the 30 GiB / 60k-file quota

Cephyr's quota will bite you if you ignore it. SIF (Apptainer's single-
file container format) is the friend that keeps you inside it.

## The quota

- **30 GiB** of bytes in your Cephyr home.
- **60,000 files** (inode count) on Cephyr.
- Hit either → new writes fail → jobs crash mid-run → you lose time.
- Check: `C3SE_quota`.

**Mimer is different** — project allocation in hundreds of GiB — so
large SIFs can also live there when shared across a team. Mimer
doesn't have the same hard file-count quota as Cephyr. See
[data-patterns.md](data-patterns.md) Pattern 4.

## Why SIF helps

A typical ML environment is **millions of files** (think `.pixi/` or
`.venv/` with pip-installed packages — every `.py`, every `__pycache__`,
every `.so`). Shoved into `$HOME`, that's game over for file count.

An Apptainer SIF is **one file**. The environment is mounted as a
read-only squashfs at run time. 2 GiB Pixi env → 1 file on disk.

## Rules of thumb

1. **No `.pixi/` or `.venv/` directories on Cephyr.** The sync script
   excludes them; keep it that way.
2. **Models live in SIFs**, not as unpacked weight trees. A 7B HF
   model unpacked = 30k+ files; baked into a SIF = 1 file.
3. **Pre-downloaded HF hub at `/mimer/NOBACKUP/Datasets/LLM/huggingface/hub/`**
   is **not** your problem (it's on a different filesystem, read-only).
   Use it; don't copy from it.
4. **Datasets belong on `/mimer/NOBACKUP/groups/<naiss-id>/`**, not
   `/cephyr/`, when the data is meaningfully large.
5. **Large shared SIFs** (a 30 GiB LLM you and teammates reuse) can
   also go on Mimer:
   `/mimer/NOBACKUP/groups/<naiss-id>/shared/sifs/llm-8b.sif` — keeps
   Cephyr clean.

## The lifecycle

### Build

On Alvis login node (recommended — fastest network for pulling base images):

```bash
cd /cephyr/users/<cid>/Alvis/my-project
apptainer build dev.sif apptainer/dev.def
```

First build pulls base layers (~3 min). Subsequent builds cached.

For deployment SIFs that bake in a model:

```bash
# See _shared/scripts/fetch-hf-model.sh
bash _shared/scripts/fetch-hf-model.sh meta-llama/Llama-3.1-8B ./models/llama3-8b.sif
```

### Transfer

**Don't rsync SIFs between laptop and cluster.** They're 2–30 GiB
binaries. Either build in place on the cluster, or use the cluster's
transfer node (vera2) for one-shot transfers:

```bash
scp my-model.sif <cid>@alvis2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/
```

### Use

```bash
apptainer run --nv my-model.sif pixi run infer
```

No `--bind .:/workspace` means "use the baked-in code". Add binds
only for external data / writable output dirs.

### Retire

When a SIF is obsolete, `rm` it. No "maybe I'll need this again" — you
can always rebuild from the `.def` file. Leaving dead SIFs around is
what kills quotas.

## Quick recipes

### "My Pixi env exploded my file count"

```bash
# Current state
du --inodes -d 2 /cephyr/users/$USER/Alvis | sort -n | tail -10

# Offenders are almost certainly .pixi/ or .venv/ — remove them, rebuild SIF
rm -rf /cephyr/users/$USER/Alvis/my-project/.pixi
apptainer build dev.sif apptainer/dev.def
# Inside jobs, use the SIF — never `pixi install` on the Cephyr filesystem directly
```

### "I want to bake a HuggingFace model into a SIF"

Use the helper (added in Phase B):

```bash
bash _shared/scripts/fetch-hf-model.sh <org/name> ./model.sif
# Implementation:
#   1. tmpdir = mktemp -d
#   2. HF_HOME=$tmpdir huggingface-cli download <org/name>
#   3. Build SIF with the tmpdir as %files
#   4. Clean tmpdir
```

After this you have a single-file SIF containing the model. No unpacked
weights anywhere on Cephyr.

### "I need to quickly switch between two model versions"

Keep them as separate SIFs:

```bash
llama3-8b-base.sif      # 16 GiB, 1 file
llama3-8b-finetuned.sif  # 16 GiB, 1 file
```

Symlink which one is "active":

```bash
ln -sf llama3-8b-finetuned.sif model.sif
apptainer run --nv model.sif pixi run eval
```

### "I'm building on laptop, running on cluster"

Prefer **not to**. Build on the cluster — WSL2 Apptainer often lacks
the user namespaces Apptainer wants. If you must:

```powershell
# Laptop (WSL2)
apptainer build -F dev.sif apptainer/dev.def
```

```powershell
# Transfer
scp dev.sif <cid>@alvis2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/my-project/
```

## Quota math: what fits in 30 GiB

| Artefact                           | Approx size      |
|------------------------------------|------------------|
| Pixi env SIF (Python + numpy + etc.)| 1–2 GiB          |
| Torch + transformers SIF            | 4–6 GiB          |
| 7B HF model weights (fp16) + env    | 14–20 GiB        |
| 13B HF model weights (fp16) + env   | 27–35 GiB        |
| Datasets (if small, fits here)      | varies           |

For anything >= 13B, bake the model into a separate SIF and rely on
the shared `/mimer/NOBACKUP/Datasets/LLM/huggingface/hub/` cache or
your `/mimer` project directory instead.

## When to ask C3SE for a quota increase

- You're well-organized, using SIFs, excluding caches, yet still near
  the cap.
- Your research genuinely needs to keep historical artifacts on Cephyr.
- Email <support@c3se.chalmers.se> with:
  - Your username
  - Current `C3SE_quota` output
  - What you'd like (e.g., "80 GiB / 200k files for 6 months")
  - Why (the scientific reason)
