# Modification — `08-hf-sif-bundle`

Actionable checklist for making this example yours. Does not
re-explain the walkthrough — that's [`usage.md`](usage.md).

## 1. Rename the package (3 files)

Rename `hf_sif_bundle` to something meaningful to your project.

**pixi.toml**

```toml
[workspace]
name = "my-bundle"              # was: hf-sif-bundle

[pypi-dependencies]
my_bundle = { path = ".", editable = true }  # was: infer_hf
```

**pyproject.toml**

```toml
[project]
name = "my-bundle"              # was: hf-sif-bundle

[tool.hatch.build.targets.wheel]
packages = ["src/my_bundle"]    # was: src/hf_sif_bundle
```

**Source directory**

```bash
mv src/hf_sif_bundle src/my_bundle
```

Then update imports. The affected files are `scripts/smoke.py`,
`scripts/info.py`, `scripts/infer.py`, `tests/test_smoke.py`, and the
`%runscript` in `apptainer/model.def` (the `from hf_sif_bundle.model
import generate` line).

```bash
grep -rln "infer_hf\|hf_sif_bundle" scripts tests src apptainer
```

Re-run tests:

```bash
pixi install
pixi run test
```

## 2. Set the Slurm account

Every sbatch has `--account=<PROJECT_ID>`. Replace in place:

**PowerShell:**

```powershell
(Get-ChildItem slurm\*.sbatch) | ForEach-Object {
    (Get-Content $_) -replace '<PROJECT_ID>', 'NAISS2024-1-234' | Set-Content $_
}
```

**bash / zsh:**

```bash
sed -i.bak 's/<PROJECT_ID>/NAISS2024-1-234/g' slurm/*.sbatch && rm slurm/*.sbatch.bak
```

Verify:

```bash
grep -H '^#SBATCH --account' slurm/*.sbatch
```

## 3. Swap the baked model — at build time

This is the distinguishing knob of the example. Two places to set
`HF_MODEL` (and optionally `HF_TOKEN`):

### Option A — via `.env` + helper script (preferred)

```ini
# .env
HF_MODEL=meta-llama/Llama-3.2-3B-Instruct
HF_TOKEN=hf_xxx                 # required for gated models
```

```bash
bash scripts/build-model-sif.sh       # reads .env, builds model.sif
```

### Option B — via `apptainer build --build-arg`

Skip `.env`, pass args directly:

```bash
apptainer build \
    --build-arg HF_MODEL=meta-llama/Llama-3.2-3B-Instruct \
    --build-arg HF_TOKEN=hf_xxx \
    model.sif apptainer/model.def
```

### Build-time vs run-time

`HF_MODEL` / `HF_TOKEN` are **build-time only**. Changing them in
`.env` after the SIF exists does nothing — you must rebuild. To
swap models cleanly:

```bash
mv model.sif model-$(date +%Y%m%d).sif  # keep old
# edit .env
bash scripts/build-model-sif.sh
```

Keep old SIFs on Mimer if you might roll back:

```bash
mv model-*.sif /mimer/NOBACKUP/groups/<naiss-id>/<cid>/sifs/
```

## 4. Pin a specific commit hash

By default the SIF bakes the current HEAD of the HF repo. For
reproducibility, add `--revision` to `huggingface-cli download` in
`apptainer/model.def`:

```diff
 huggingface-cli download "${HF_MODEL}" \
+    --revision "${HF_REVISION}" \
     --local-dir /opt/model --local-dir-use-symlinks False
```

And add `HF_REVISION` to `%arguments`:

```diff
 %arguments
     HF_MODEL=google/gemma-2-2b-it
     HF_TOKEN=
+    HF_REVISION=main
```

Then pass `--build-arg HF_REVISION=<hash>` at build time.

## 5. Extend `.env`

Project-specific keys go in `.env` and get a matching reader in
`src/<pkg>/config.py`. Example — a second prompt template path:

```ini
# .env
SYSTEM_PROMPT_FILE=/data/prompts/system.txt
```

```python
# src/<pkg>/config.py
def system_prompt_file() -> Path | None:
    v = _env("SYSTEM_PROMPT_FILE")
    return Path(v) if v else None
```

## 6. Add new pixi tasks

Edit `[tasks]` in `pixi.toml`. The stock tasks run inside the SIF
via `apptainer run --nv model.sif pixi run <task>`:

```toml
[tasks]
smoke       = "python scripts/smoke.py"
info        = "python scripts/info.py"
infer       = "python scripts/infer.py"
infer-batch = "python scripts/infer_batch.py"   # new
test        = "pytest -q tests/"
lint        = "python -m compileall src scripts tests"
```

## 7. Add a new sbatch variant

Copy `slurm/gpu-t4.sbatch` for a different GPU / walltime:

| File | `--gpus-per-node` | `--time` | Typical model |
|------|-------------------|----------|---------------|
| `gpu-t4.sbatch`    | `T4:1`    | `0-00:30:00` | < 3 B params |
| `infer-a40.sbatch`   | `A40:1`   | `0-02:00:00` | 3–13 B |
| `infer-a100.sbatch`  | `A100:1`  | `0-04:00:00` | 13–40 B |
| `build-model.sbatch` | `none`    | `0-01:00:00` | builds the SIF itself on login-adjacent CPU node |

For a `build-model.sbatch` that runs the build on a compute node
(useful for big models where the login node times out): set `SIF=`
to empty, and in the body call `bash scripts/build-model-sif.sh`
instead of `apptainer run`.

## 8. What NOT to change

- `MODEL_DIR=/opt/model` — hardcoded in `apptainer/model.def`'s
  `%post` and `%environment`. Changing only in `.env` desynchronises
  the build and produces a broken SIF.
- `local_files_only=True` in `src/<pkg>/model.py` — removing it
  would let `transformers` reach the Hub at run time, defeating the
  "offline" property of the baked SIF.
- `HF_HUB_OFFLINE=1` / `TRANSFORMERS_OFFLINE=1` in
  `apptainer/model.def` `%environment` — defence-in-depth for the
  offline guarantee.
- `generate()` return shape `{text, model, device, usage}` — tier-2
  multi-provider examples consume this contract.
