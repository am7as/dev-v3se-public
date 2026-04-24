# `22-reconstruct-retrain-infer` — folder layout

```
22-reconstruct-retrain-infer/
├── README.md                   why-this-template + quickstart
├── .env.example                env vars + training + surgery config
├── .gitignore
├── docker-compose.yml          laptop dev stack
├── pixi.toml                   pixi tasks + deps (torch, accelerate, transformers, sklearn)
├── pyproject.toml              Python packaging + wheel target
├── apptainer/
│   ├── dev.def                 dev SIF — used for surgery + train + eval
│   └── app.def                 deployment SIF (code baked, no weights)
├── configs/
│   ├── surgery.yaml            declarative surgery spec (operation + num_labels + …)
│   └── accelerate/
│       ├── single.yaml         single-GPU (shipped example: 6-class classifier)
│       ├── ds_zero2.yaml       DeepSpeed ZeRO-2
│       ├── ds_zero3.yaml       DeepSpeed ZeRO-3
│       └── fsdp.yaml           FSDP
├── scripts/                    entrypoints for `pixi run <task>`
│   ├── smoke.py                pixi run smoke   — offline, asserts imports
│   ├── info.py                 pixi run info    — prints resolved env
│   ├── surgery.py              pixi run surgery — apply surgery.yaml → new base
│   ├── train.py                accelerate-launched retrain on target dataset
│   └── eval.py                 pixi run eval    — classification metrics report
├── src/reco/
│   ├── __init__.py
│   ├── config.py               path + training + surgery env resolver
│   ├── surgery.py              architecture mutations (replace_classification_head, …)
│   ├── train.py                core retrain loop (HF Trainer + sklearn metrics)
│   └── evaluate.py             classification pipeline + acc/F1/confusion matrix
├── slurm/
│   ├── surgery.sbatch          CPU-only (20 min) — surgery is structural, not compute-bound
│   ├── train.sbatch            1× T4 retrain (4 h / 32 G / accelerate)
│   ├── eval.sbatch             1× T4 eval (30 min / 16 G)
│   └── bundle.sbatch           CPU (30 min) — heredoc `.def` → standalone SIF
├── tests/
│   └── test_smoke.py           pytest — config + surgery yaml parse + import smoke
└── docs/
    ├── setup.md                first-time setup (laptop + Alvis)
    ├── usage.md                full-pipeline walkthrough (surgery → train → eval → bundle)
    ├── modification.md         how to add surgery operations / swap datasets
    ├── structure.md            (this file)
    └── troubleshooting.md      per-stage failure modes
```

## Key files, one paragraph each

### `apptainer/dev.def` and `apptainer/app.def`

Pixi-based containers. `dev.def` is the workhorse for surgery +
train + eval. `app.def` bakes the training code for reproducibility
but does not bake weights — the deployable artefact is produced by
`slurm/bundle.sbatch`, which builds a third SIF per-checkpoint.

### `configs/surgery.yaml`

Declarative surgery spec. The shipped example:

```yaml
operation: replace_classification_head
num_labels: 6
freeze_base: false
```

`src/reco/surgery.py` dispatches on `operation`. To add a new
operation (adapter insertion, LoRA-in-specific-blocks, swap
attention impl, freeze by depth), add a handler there and a new
`operation:` value to `surgery.yaml`.

### `configs/accelerate/single.yaml`

`distributed_type: NO`, `num_processes: 1`, bf16. Used by default in
the shipped example (a small DistilBERT classifier). `ds_zero2.yaml`
/ `ds_zero3.yaml` / `fsdp.yaml` mirror the tier-3 `21-distributed-
finetune` configs for when the reconstructed model is large enough to
need distributed training.

### `slurm/surgery.sbatch`

20-minute CPU-only job. Surgery is a structural transformation —
load the base, mutate the architecture, save the result. No training,
no GPU. Writes the surgeried model to
`$RESULTS_DIR/surgeried/<utc-stamp>/`.

### `slurm/train.sbatch`

4-hour `T4:1` job. Expects `MODEL=/path/to/surgeried/<ts>/` via
`--export`. Runs `accelerate launch --config_file
configs/accelerate/${ACCELERATE_CONFIG:-single}.yaml scripts/train.py
--model "$MODEL"`. For a 6-class text classifier on distilbert +
`emotion` dataset, 3 epochs fit easily in the 4-h budget.

### `slurm/eval.sbatch`

30-minute `T4:1`. Expects `CKPT=/path/to/checkpoint` via `--export`.
Runs the evaluation script which uses a `pipeline("text-classification",
…)` plus sklearn metrics, producing `$RESULTS_DIR/eval_report.json`.

### `slurm/bundle.sbatch`

30-minute CPU-only job. **Unlike `13-train-infer-pipeline`, this
template generates the `.def` inline via heredoc** — no `.def.tpl`
file. Takes `CKPT=/path/to/checkpoint`, writes
`/tmp/reco-bundle-<ts>.def`, runs `apptainer build $OUT /tmp/....def`.
The bundle copies the full checkpoint into `/opt/model` and
`HF_MODEL_SNAPSHOT` points at it. Output at
`$PWD/results/bundles/reco-<ts>.sif` — **note** this path default
doesn't go through `$RESULTS_DIR`; in practice on Alvis the bundled
SIF belongs on Mimer and you should edit this sbatch to point at
`$MIMER_PROJECT_PATH/bundles/` before first real use.

### `src/reco/config.py`

Env resolver. Path helpers + training hyperparams + `num_labels()` +
`surgery_config_path()` (default `configs/surgery.yaml`).

### `src/reco/surgery.py`

The interesting one. `replace_classification_head(base, num_labels,
out_dir, freeze_base)` loads the backbone via
`AutoModelForSequenceClassification.from_pretrained(...,
ignore_mismatched_sizes=True)` — HF auto-constructs a fresh head of
shape `(hidden_size, num_labels)`. If `freeze_base=True`, only
`classifier.*` params keep `requires_grad`. Writes a **full HF-format
model directory** (config.json + model.safetensors + tokenizer).
`run()` reads `surgery.yaml`, dispatches on `operation`, saves to
`$RESULTS_DIR/surgeried/<ts>/` along with `surgery_summary.json`.

### `src/reco/train.py`

HF `Trainer` retraining loop. Loads the surgeried model, tokenises
the HF dataset, runs 3 epochs with eval-on-epoch and save-on-epoch
(`save_total_limit=2`). Reports accuracy + macro-F1 via sklearn.
Writes checkpoint + `run_summary.json` to
`$RESULTS_DIR/checkpoints/<ts>/`.

### `src/reco/evaluate.py`

Uses `transformers.pipeline("text-classification", …)` — simpler
than the generative eval in `21`. Loads checkpoint, iterates the
test split, computes accuracy + macro-F1 + confusion matrix. Writes
`$RESULTS_DIR/eval_report.json`.

### `scripts/surgery.py`, `train.py`, `eval.py`

Thin CLI wrappers. `surgery.py` prints the next-step command (the
full `sbatch --export=ALL,MODEL='…' slurm/train.sbatch` line) so the
pipeline is self-documenting. `train.py` accepts `--model` or the
`MODEL` env var. `eval.py` takes `--ckpt` + optional `--split`.

### `docker-compose.yml`

Laptop dev stack. Same shape as every other template.

### `tests/test_smoke.py`

Asserts config defaults, `surgery.yaml` parses, `surgery._read_surgery_config`
works. No surgery, no training. < 1 s.

## Storage model — four artefacts at three life-stages

Four distinct persisted artefacts, each with its own size profile:

| Artefact             | Size              | Produced by       | Storage tier     |
|----------------------|-------------------|-------------------|------------------|
| Surgeried model dir  | ~size of base     | `surgery.sbatch`  | **Mimer project** (`$RESULTS_DIR/surgeried/<ts>/`) |
| Training checkpoint  | ~size of base     | `train.sbatch`    | **Mimer project** (`$RESULTS_DIR/checkpoints/<ts>/`) |
| Eval report JSON     | KB                | `eval.sbatch`     | **Mimer project** (`$RESULTS_DIR/eval_report.json`) |
| Bundled SIF          | ~size of base + pixi env | `bundle.sbatch` | **Mimer project** (after you fix the default path) |

A distilbert-base-uncased surgery cycle (the shipped example):
surgeried dir ~260 MB, checkpoint ~260 MB × 2 (save_total_limit=2),
eval report ~10 KB, bundle SIF ~2 GB. All manageable. Scale up to a
7B-param reconstruction and each artefact grows to ~16 GB.

### Canonical bind mounts

| Container path | Laptop host                      | Alvis host                                        | Storage tier                |
|----------------|----------------------------------|---------------------------------------------------|-----------------------------|
| `/workspace`   | `.`                              | `/cephyr/users/<cid>/Alvis/<project>/`            | **Cephyr** — code + SIFs    |
| `/data`        | `${DATA_HOST:-../data}`          | `/mimer/NOBACKUP/groups/<naiss-id>/data/`         | **Mimer project** — JSONLs if used |
| `/results`     | `${RESULTS_HOST:-../results}`    | `$MIMER_PROJECT_PATH/results/`                    | **Mimer project** — surgeried/, checkpoints/, eval_report.json |
| `/models`      | `${MODELS_HOST:-../models}`      | `/mimer/NOBACKUP/groups/<naiss-id>/models/`       | **Mimer project**           |
| `$HF_HOME`     | `/workspace/.hf-cache`           | `$MIMER_PROJECT_PATH/.hf-cache`                   | **Mimer project** — base model snapshot |

### Runtime-vs-build resolution

- **Build time** (`apptainer build dev.sif …`): no weights, no
  datasets. Just code + pixi env.
- **Compose up** (laptop): standard bind-mount config. Small
  distilbert fits entirely in the in-repo `.hf-cache/`.
- **Surgery sbatch**: reads base from `$HF_HOME` (downloaded on
  first use), writes surgeried model to
  `$RESULTS_DIR/surgeried/<ts>/` on Mimer.
- **Train sbatch**: reads the surgeried model (path passed via
  `--export=ALL,MODEL=…`), writes checkpoints to
  `$RESULTS_DIR/checkpoints/<ts>/` on Mimer.
- **Eval sbatch**: reads one specific checkpoint, writes one
  eval report.
- **Bundle sbatch**: copies a checkpoint tree into a new SIF at
  build time. **Watch the default output path** (`$PWD/results/bundles/`)
  — edit to `$MIMER_PROJECT_PATH/bundles/` before real use, matching
  the pattern in `13-train-infer-pipeline`.
- **Neither `train.sbatch` nor `surgery.sbatch` has an explicit
  Mimer branch** (unlike `05` / `13`). Both default `HF_HOME` /
  `RESULTS_DIR` to `$PWD/...` — safe on laptop, dangerous on Alvis.
  Set both explicitly in `.env` before submission (mirror the
  pattern in `21-distributed-finetune/docs/structure.md`).

## Design invariants

- **Surgery is declarative.** All the "what did you change?"
  information lives in `configs/surgery.yaml`. No architecture
  mutation is hidden in the training loop.
- **Surgery output is a drop-in HF model.** Once written, the
  surgeried directory is loadable by any
  `AutoModel.from_pretrained(...)` — it's a fully HF-format
  checkpoint.
- **Retrain is ordinary HF `Trainer`.** After surgery, nothing about
  the retrain loop is special — standard CSV of gotchas applies.
- **Four sbatches, one pipeline.** `surgery` → `train` → `eval` →
  `bundle`. Each consumes the previous's output path; all outputs
  live on Mimer.
- **Bundle default path is a known bug.** The shipped `bundle.sbatch`
  writes to `$PWD/results/bundles/` — fine on laptop, wrong on
  Alvis. Override before production use. The library audit
  (`_checklist/`) tracks this.
