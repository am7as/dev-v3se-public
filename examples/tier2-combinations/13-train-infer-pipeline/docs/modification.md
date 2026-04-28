# Modification — `13-train-infer-pipeline`

## Include the base-model weights in the bundle

Default bundle references the base model by HF id — the SIF downloads
weights at first run. For fully offline reproducibility, bake weights in:

1. Fetch them once with `_shared/scripts/fetch-hf-model.sh`.
2. Edit `apptainer/bundle.def.tpl` to add:
   ```
   %files
       /path/to/weights /opt/base-model
   %environment
       export HF_MODEL_SNAPSHOT=/opt/base-model
   ```

Trades off size (+ model bytes) for full offline usability.

## Use a different trainer (e.g., DPO, ORPO)

Replace the `Trainer` in `src/train_infer/train.py` with `trl.DPOTrainer`
etc. Same input dataset shape, different loss function. The bundler
doesn't care.

## Multiple adapters in one bundle

Change the `%files` section to copy multiple adapter dirs under
`/opt/adapters/name-a`, `/opt/adapters/name-b`. Extend `scripts/infer.py`
to pick one by `--adapter-name`.

## Log training data into the bundle (for provenance)

Add to `apptainer/bundle.def.tpl`:

```
%files
    /path/to/dataset.jsonl /opt/dataset.jsonl
```

So the SIF contains the exact training data used. Great for
reproducibility, expensive on size.

## What NOT to change

- The `/opt/adapter` convention — other templates and the bundle def
  expect this path.
- The `BUNDLED_ADAPTER_DIR` env var.
- Adapter format — PEFT/LoRA standard layout.
