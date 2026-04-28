# Modification — `12-multi-source-data`

## Add a source

1. `src/data_multi/sources/<name>.py`:
   ```python
   NAME = "my_source"
   def resolve(dataset=None): ...  # return a Path
   def load(dataset, split="train"): ...  # optional, for non-filesystem sources
   ```
2. Register in `sources/__init__.py`.
3. Add to `configs/sources.yaml`.
4. If it needs extra deps (e.g., `boto3` for S3), add to `pixi.toml`.

## Handle other HF dataset shapes

Default `summarize_hf_dataset()` assumes a flat schema. For nested
(image/text pairs, spans, etc.), extend `processing.py` to report the
fields you care about.

## Pre-mount a GCS bucket on the host

Easier for laptop dev than mounting inside the container:

```bash
rclone mount waymo:open /mnt/waymo --daemon --read-only
```

Then `.env`: `DATA_HOST=/mnt/waymo`, `DATASET_SOURCE=local`. No GCS
provider needed.

## Adapt for on-the-fly download

For sources that must stream (e.g., S3, GCS without FUSE), change
`router.resolve()` to return a generator / an iterator over records
instead of a Path. Keep the contract clean by adding a `stream=True`
kwarg.

## What NOT to change

- Source module interface: `NAME` + `resolve(dataset)`.
- Container paths.
- Env-var names.
