# Modification — `04-data-cephyr`

## Point at your own data

**Laptop:**
```ini
# .env
DATA_HOST=D:/my-dataset-root
```

**Alvis:** edit `slurm/process-cpu.sbatch` and uncomment pattern B (private
Cephyr) or C (shared `/mimer`).

## Process a non-CSV format

Swap the reader in `src/data_cephyr/processing.py`:

```python
# for Parquet
df = pd.read_parquet(path)

# for JSON lines
df = pd.read_json(path, lines=True)

# for Hugging Face datasets
from datasets import load_dataset
ds = load_dataset("parquet", data_files=str(path))
df = ds["train"].to_pandas()
```

## Stream large files

`pd.read_csv` loads everything into memory. For >10 GB files, switch to
chunking:

```python
for chunk in pd.read_csv(path, chunksize=100_000):
    process_chunk(chunk)
```

Or use `polars` / `duckdb` for out-of-core SQL on CSVs:

```toml
# pixi.toml
[pypi-dependencies]
duckdb = "*"
```
```python
import duckdb
duckdb.sql("SELECT COUNT(*), AVG(temperature) FROM '/data/sample/*.csv'").show()
```

## Bring in a non-V3SE shared source

Mount an S3 bucket with rclone:

```bash
rclone mount myremote:bucket /mnt/s3 &
# Then:
apptainer run --bind .:/workspace --bind /mnt/s3:/data "$SIF" pixi run process
```

See [../../../docs/data-patterns.md](../../../docs/data-patterns.md) for
all the cloud patterns.

## What NOT to change

- Container path `/data` for inputs, `/results` for outputs.
- `process()` returning a dict with `file_count`, `total_rows` —
  template `12` reads this shape.
