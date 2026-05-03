# `05-train-lora` — folder layout

```
05-train-lora/
├── README.md                   why-this-template + quickstart
├── .env.example                env vars the template reads, with comments
├── .gitignore                  keeps .env, results/, *.sif, .pixi/, .hf-cache/ out
├── docker-compose.yml          laptop dev stack
├── pixi.toml                   pixi tasks + deps (torch+cu121, transformers, peft, trl)
├── pyproject.toml              Python packaging + wheel target
├── apptainer/
│   ├── dev.def                 dev SIF (code bind-mounted in) — laptop + Alvis
│   └── app.def                 deployment SIF (code baked in)
├── configs/
│   └── config.toml             layout config (container paths)
├── scripts/                    entrypoints for `pixi run <task>`
│   ├── smoke.py                pixi run smoke   — offline, asserts imports
│   ├── info.py                 pixi run info    — prints resolved env
│   ├── train.py                pixi run train   — LoRA finetune → adapter dir
│   └── infer.py                pixi run infer   — load adapter, generate text
├── src/train_lora/
│   ├── __init__.py
│   ├── config.py               path + training-hyperparam env resolver
│   └── train.py                core: load model → wrap with LoRA → Trainer → save
├── slurm/
│   └── train-t4.sbatch         1× T4 training job (1 h / 32 G / `--nv`)
├── tests/
│   └── test_smoke.py           pytest — config + import smoke, no GPU needed
└── docs/
    ├── setup.md                first-time setup (laptop + Alvis)
    ├── usage.md                step-by-step golden path
    ├── modification.md         how to adapt to your project
    ├── structure.md            (this file)
    └── troubleshooting.md      known C3SE-specific issues
```

## Key files, one paragraph each

### `apptainer/dev.def` and `apptainer/app.def`

Pixi-based containers. `dev.def` installs system tools + expects the
project bind-mounted at `/workspace`. `app.def` copies `src/` +
`scripts/` + `configs/` into `/workspace` and runs `pixi install` at
build time. The pixi env is big here (torch + cu121 wheels), so builds
take a few minutes — but the resulting SIF is self-contained and
reproducible. **Weights are never baked into the SIF** — they flow
through `HF_HOME` at run time.

### `slurm/train-t4.sbatch`

1-hour `T4:1` job (`--cpus-per-task=4`, `--mem=32G`, `--nv`). The sbatch
is the canonical reference for Cephyr/Mimer handling in a training
context — read it carefully:

```bash
if [ -n "${MIMER_USER_DIR:-}" ]; then
    export HF_HOME="${HF_HOME:-${MIMER_USER_DIR}/.hf-cache}"
    export RESULTS_DIR="${RESULTS_DIR:-${MIMER_USER_DIR}/results}"
else
    echo "WARNING: MIMER_USER_DIR unset — falling back to \$PWD. On Alvis this will hit the Cephyr quota." >&2
    ...
fi
```

If `MIMER_USER_DIR` is set (Alvis), `HF_HOME` and `RESULTS_DIR` go
to Mimer project. If unset (laptop), they fall back to `$PWD` and the
sbatch logs a warning — safe on laptop, dangerous on Alvis.
`--account=<PROJECT_ID>` placeholder must be replaced before first
submission.

### `src/train_lora/config.py`

Env resolver. In addition to path helpers (`data_dir`, `results_dir`)
it exposes training knobs: `model_id()`, `model_snapshot()`,
`dataset_id()`, `lora_r()`, `lora_alpha()`, `lora_dropout()`,
`num_epochs()`, `batch_size()`, `learning_rate()`. All read from env
with sensible defaults for a laptop smoke run.

### `src/train_lora/train.py`

The core. `run()` resolves the base model via
`model_snapshot() or model_id()` (snapshot path wins — the
pre-downloaded-weights story from `03-hf-shared-hub`). Loads tokenizer
+ model, wraps with `peft.LoraConfig`, loads the dataset (`HF_DATASET`
env, JSONL path, or the shipped 5-row in-memory sample), tokenizes,
trains with `transformers.Trainer`, and **saves only the LoRA adapter**
(a few MB) plus `run_summary.json` to
`$RESULTS_DIR/adapters/<utc-stamp>/`. Base weights are not re-saved.

### `scripts/train.py`

Thin CLI wrapper around `train_lora.train.run()`. Prints the run
summary as JSON and the adapter path — the path is what `pixi run
infer` needs.

### `scripts/infer.py`

Loads the base model + the adapter via `PeftModel.from_pretrained`,
runs `model.generate(...)` on a prompt, prints the decoded text. Takes
`--adapter-dir` (required), `--prompt` (required), `--max-new-tokens`
(default 80). Auto-detects CUDA for the forward pass.

### `scripts/smoke.py` and `scripts/info.py`

`smoke.py` asserts torch / transformers / peft / datasets all import,
prints CUDA availability — no model load, no training. `info.py` dumps
resolved env + hyperparams as JSON.

### `configs/config.toml`

Static container-path layout. Training hyperparams live in `.env`, not
here — they change per run; paths are structural.

### `docker-compose.yml`

Laptop dev stack. Builds `../../_shared/docker/Dockerfile.dev`,
bind-mounts the project at `/workspace`, maps `$DATA_HOST` / `$RESULTS_HOST` /
`$MODELS_HOST`, keeps a `pixi_env` volume. The GPU stanza is commented
out by default — uncomment on a Linux host with `nvidia-container-toolkit`.

### `tests/test_smoke.py`

Asserts config defaults + imports work. Does **not** train — running
the real training loop as a unit test would take minutes and need a
GPU. Runs under `pixi run test` in < 1 s.

## Storage model — training has the strictest demands

Training amplifies every Cephyr/Mimer mistake:

- Model weights pulled from Hugging Face can be tens of GB.
- `HF_HOME` accumulates snapshots + blobs — thousands of small files.
- Training checkpoints (if enabled) are multi-GB each.
- The LoRA adapter itself is small (MB), but the cache behind it is not.

| Container path | Host path on laptop              | Host path on Alvis                                | Storage tier                        |
|----------------|----------------------------------|---------------------------------------------------|-------------------------------------|
| `/workspace`   | `.` (project root)               | `/cephyr/users/<cid>/Alvis/<project>/`            | **Cephyr** — code + SIF only        |
| `/data`        | `${DATA_HOST:-../data}`          | `/mimer/NOBACKUP/groups/<naiss-id>/data/`         | **Mimer project** — training JSONL, HF datasets cache |
| `/results`     | `${RESULTS_HOST:-../results}`    | `$MIMER_USER_DIR/results/`                    | **Mimer project** — `adapters/<ts>/` |
| `/models`      | `${MODELS_HOST:-../models}`      | `/mimer/NOBACKUP/groups/<naiss-id>/models/`       | **Mimer project** — pre-downloaded base weights (optional) |
| `$HF_HOME`     | `/workspace/.hf-cache`           | `$MIMER_USER_DIR/.hf-cache`                   | **Mimer project** — HF snapshots, blobs |

The default `HF_HOME=/workspace/.hf-cache` in `.env.example` is a
**laptop-only** default. On Alvis, the sbatch explicitly overrides it
to `$MIMER_USER_DIR/.hf-cache`. Leaving the default there would
write snapshots into the bind-mounted project root — which on Alvis is
Cephyr. A single Llama-8B snapshot (~16 GB, thousands of files) would
exceed the 30 GiB quota and the 60k file cap simultaneously.

### Runtime-vs-build resolution

- **Build time** (`apptainer build …`, `docker compose build`): no
  weights, no datasets, no cache. Only code + pixi deps + system tools.
- **Compose up** (laptop): `.env` drives `HF_HOME` to the in-repo
  `.hf-cache/` (git-ignored), weights get downloaded once per base
  model. Small enough to live on the laptop next to the code.
- **sbatch submit** (Alvis): the sbatch branches on
  `MIMER_USER_DIR`. Set it in `.env` (pattern:
  `/mimer/NOBACKUP/groups/<naiss-id>/<project>/`) before first
  submission — the branch is what keeps you out of quota trouble.
- **Adapter output**: always under
  `$RESULTS_DIR/adapters/<utc-stamp>/`. On Alvis that lands on Mimer;
  `pixi run infer --adapter-dir …` on the same machine picks it up
  directly.

## Design invariants

- **Save the adapter, not the base.** `model.save_pretrained()` on a
  `PeftModel` writes only LoRA weights. Never re-save the full base.
- **`HF_HOME` is a `.env` field, not a code default.** The one line in
  `.env.example` (`HF_HOME=/workspace/.hf-cache`) is for laptop only;
  `train-t4.sbatch` overrides it for Alvis.
- **Cache lives on Mimer.** 8B-param base = ~16 GB = instant Cephyr
  quota kill. No exceptions.
- **The adapter is the deliverable.** MB-scale output on Mimer is
  trivial to rsync back to the laptop via
  `_shared/scripts/sync-from-cephyr.sh` (wrapper-layer tooling).
- **Training defaults are laptop-safe.** `HF_MODEL=sshleifer/tiny-gpt2`
  + 5-row in-memory sample = `pixi run train` works on a MacBook in
  under a minute. Swap `HF_MODEL` and `HF_DATASET` in `.env` for a
  real run on Alvis.
