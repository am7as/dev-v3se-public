# Storage model

Three storage systems are in play. Get the mental model right once
and every subsequent command is obvious.

> **Both Cephyr and Mimer are writable and auto-visible from Alvis
> compute nodes.** You can put code in either, data in either, or
> mix the two. The recommendations below are *defaults that minimize
> quota surprises* — not hard rules. If you have a tiny code repo
> and a huge dataset, the default lines up naturally (code on
> Cephyr, data on Mimer). If you have an enormous codebase and
> minimal data, flip it. If you want one unified location per
> project, put everything on Mimer. The code reads from env-driven
> paths; only `.env` changes.

## The three systems

### 1. Cephyr — backed up, strict quota

- Path on cluster: `/cephyr/users/<cid>/Alvis/<project>/`
- Size: **30 GiB hard cap** AND **60,000 files hard cap**
- Backed up: yes
- Auto-visible from Alvis compute nodes (no explicit bind needed)

**Default role**: source code, configs, small logs.

**Good fit:** source code, `pixi.toml`, `pixi.lock`,
`docker-compose.yml`, `apptainer/*.def`, `slurm/*.sbatch`,
`configs/`, `.env` (never committed), `.sif` files while small
(< 2 GiB), small logs, job stdout/stderr.

**Avoid here** (moves to Mimer): model weights, large datasets,
checkpoint dumps, `.pixi/` / `.venv/` (rebuild them inside
containers instead), `.hf-cache/`, `.ollama/`, `results/` if
results are big, `wandb/`, `mlruns/`.

**Flexibility**: you *can* put data on Cephyr if it's tiny and you
want it versioned next to the code. You *can* put the whole
project (code + small data) on Cephyr if you stay under the quota.
Treat the "what goes here" list as the default mental model, not a
law.

Check your usage any time:

```bash
ssh alvis C3SE_quota
```

### 2. Mimer project — big, writable, per-project, no backups

- Path on cluster: `/mimer/NOBACKUP/groups/<naiss-id>/`
- Size: **per-project allocation** in GiB (typical: 800 GiB)
- Backed up: **no** — keep irreplaceable originals elsewhere
- Auto-visible from Alvis compute nodes

**Default role**: data, weights, checkpoints, big results.

**Good fit:** datasets you own, trained model weights,
checkpoints, big results (evaluation dumps, predictions),
HuggingFace caches (`HF_HOME`), Ollama model cache
(`OLLAMA_MODELS`), LM Studio cache, wandb/mlflow run logs when
large, SIFs you want to share across your team.

**Flexibility**: you *can* put code on Mimer if, for example, your
repo is unusually big (> 30 GiB or > 60k files — rare but
possible with heavy vendored deps or generated artefacts). You
*can* put a whole project on Mimer. The only thing Mimer cannot
give you that Cephyr does is backups.

Suggested sub-layout:

```
/mimer/NOBACKUP/groups/<naiss-id>/
├── shared/             # team-shared data + models, writable by all
│   ├── datasets/
│   └── models/
├── sifs/               # large SIFs reused across team
└── <cid>/              # your personal scratch under this project
    └── <project>/
        ├── hf-cache/
        ├── ollama/
        ├── checkpoints/
        ├── results/
        └── wandb/
```

Check usage in the NAISS portal:

```
Mimer @ C3SE
/mimer/NOBACKUP/groups/naissXXXX-X-XXX    800    GiB    ...   <percent-used> %
```

### 3. Mimer shared — read-only C3SE mirrors

- Path on cluster: `/mimer/NOBACKUP/Datasets/`
- Size: — (doesn't count against your allocation)
- Backed up: managed by C3SE
- Auto-visible from Alvis compute nodes

**What's here**: commonly-used datasets and a pre-downloaded
HuggingFace hub:

- `/mimer/NOBACKUP/Datasets/nuScenes/`
- `/mimer/NOBACKUP/Datasets/ImageNet/`
- `/mimer/NOBACKUP/Datasets/LLM/huggingface/hub/`
- … and more; see the C3SE documentation for the current list.

Mount with `:ro` when binding into containers — defensive but
harmless (Mimer shared is read-only anyway).

## Default placement per artefact

Defaults — override when your project has unusual sizing.

| Artefact                       | Default        | Alternatives / notes |
|--------------------------------|----------------|----------------------|
| Source code + configs          | Cephyr         | Mimer if the repo is huge |
| `.env`                         | Cephyr (local) | never committed; per-machine |
| `.sif` (small, < 2 GiB)        | Cephyr         | OR Mimer if team-shared |
| `.sif` (large, >= 2 GiB)       | Mimer          | especially if team-shared |
| Dataset                        | Mimer or Mimer-shared | read-only shared wins when available |
| Model weights                  | Mimer          | Cephyr quota doesn't fit unpacked trees |
| HF cache (`HF_HOME`)           | Mimer          | `$HOME` default = quota death |
| Ollama cache (`OLLAMA_MODELS`) | Mimer          | same |
| LM Studio cache                | Mimer          | same |
| Pixi env (`.pixi/`)            | inside SIF     | NEVER on Cephyr or Mimer directly — bake into SIF, not as unpacked tree |
| Checkpoints                    | Mimer          | size + no-backup accepted |
| Small job logs, manifests      | Cephyr         | alongside code is fine |
| Big eval dumps, wandb runs     | Mimer          | easily gigabytes |

**The env-driven principle**: the code reads paths from `.env`. To
move an artefact between Cephyr and Mimer, change the `.env` entry
and re-run — no code change, no rebuild.

## Common misconfigurations (and how they bite)

- **`HF_HOME` defaulting to `~/.cache/huggingface/`** on Alvis →
  blows the 60,000-file cap on the first large model download.
  **Fix:** always set `HF_HOME=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/hf-cache`.

- **`pip install --user`** on a login node → `~/.local/` fills
  Cephyr in a dozen deps. **Fix:** run `pip install` only inside
  a SIF or Pixi env; never at the login-node shell.

- **Building a SIF inside the project directory on Cephyr** → 15+
  GiB temporary build cache. **Fix:** build on the login node with
  `APPTAINER_CACHEDIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/apptainer-cache`,
  or build on laptop and push the `.sif`.

- **`.pixi/` ending up on Cephyr** from a `pixi install` ran
  outside a container → tens of thousands of files. **Fix:** treat
  Pixi as SIF-internal. The `sync-to-cephyr.sh` helper excludes
  `.pixi/` explicitly.
