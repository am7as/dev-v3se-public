# Modification — `03-hf-shared-hub`

Actionable checklist. Follow top-to-bottom the first time; come back
for targeted edits later. Does not re-explain the walkthrough —
that's [`usage.md`](usage.md).

## 1. Rename the package (3 files)

Rename `hf_shared_hub` to something your team will recognise (e.g.
`my_inference`). The name must appear in exactly three places — if
any one is missed, `pixi install` or `pytest` will fail.

**pixi.toml**

```toml
[workspace]
name = "my-inference"           # was: hf-shared-hub

[pypi-dependencies]
my_inference = { path = ".", editable = true }   # was: infer_hf
```

**pyproject.toml**

```toml
[project]
name = "my-inference"           # was: hf-shared-hub

[tool.hatch.build.targets.wheel]
packages = ["src/my_inference"] # was: src/hf_shared_hub
```

**Source directory**

```bash
mv src/hf_shared_hub src/my_inference
```

Then update every `from infer_hf` / `from hf_shared_hub` import. In
the stock scaffold these live in `scripts/smoke.py`, `scripts/info.py`,
`scripts/infer.py`, and `tests/test_smoke.py`.

```bash
# from the project root
grep -rln "infer_hf\|hf_shared_hub" scripts tests src
```

Re-run the test to confirm:

```bash
pixi install
pixi run test
```

## 2. Set the Slurm account

Every sbatch has `--account=<PROJECT_ID>` as a placeholder. Replace
in place:

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

## 3. Swap the model snapshot

This example's distinguishing property is that it **only** loads from
`HF_MODEL_SNAPSHOT`. To change models:

```bash
# 1. List what C3SE mirrors
ssh alvis "ls /mimer/NOBACKUP/Datasets/LLM/huggingface/hub/" | grep -i <your-model>

# 2. List snapshots for that model
ssh alvis "ls /mimer/NOBACKUP/Datasets/LLM/huggingface/hub/models--<org>--<name>/snapshots/"

# 3. Pick a commit hash, set in .env
#    HF_MODEL_SNAPSHOT=/mimer/.../models--<org>--<name>/snapshots/<hash>/
```

If your target model isn't in the mirror, this example is the wrong
fit — migrate to `../08-hf-sif-bundle/` or `../09-hf-hub-streaming/`.

## 4. Extend `.env`

Add project-specific keys below the stock block in `.env`. Match the
contract used by `src/<pkg>/config.py` — anything you add there needs
a matching `_env()` call, and a default in `configs/config.toml` if
you want `pixi run info` to show it.

Example — add a system-prompt path:

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

## 5. Add new pixi tasks

Edit `[tasks]` in `pixi.toml`:

```toml
[tasks]
smoke       = "python scripts/smoke.py"
info        = "python scripts/info.py"
infer       = "python scripts/infer.py"
infer-batch = "python scripts/infer_batch.py"   # new
bench       = "python scripts/bench.py"         # new
test        = "pytest -q tests/"
lint        = "python -m compileall src scripts tests"
```

Drop the matching script under `scripts/`. Make sure it imports from
your renamed package, not the stock one.

## 6. Add a new sbatch variant

Copy `slurm/gpu-t4.sbatch` and edit the GPU flavour / walltime.
Common variants:

| File | `--gpus-per-node` | `--time` | Use |
|------|-------------------|----------|-----|
| `gpu-t4.sbatch`   | `T4:1`         | `0-00:30:00` | default smoke + short runs |
| `infer-a40.sbatch`  | `A40:1`        | `0-02:00:00` | mid-size models (7–13 B) |
| `infer-a100.sbatch` | `A100:1`       | `0-04:00:00` | 30+ B models |
| `infer-v100.sbatch` | `V100:1`       | `0-01:00:00` | fp16-friendly, older GPUs |

After copying, adjust `--mem` proportionally (A100 usually wants
`--mem=64G` or more) and rename the job (`--job-name=`) so logs are
distinguishable.

## 7. What NOT to change

- `generate()` return shape `{text, model, device, usage}` — tier-2
  examples compose many providers and rely on this contract.
- The env-var names `HF_MODEL_SNAPSHOT`, `HF_DEVICE`, `HF_DTYPE`,
  `HF_MAX_NEW_TOKENS`.
- `local_files_only=True` in `src/<pkg>/model.py` — removing it would
  silently fall back to Hub streaming, defeating the shared-hub
  premise. For streaming behaviour use `../09-hf-hub-streaming/`.
