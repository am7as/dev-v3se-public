# Modification — `05-train-lora`

## Switch to a real model

```ini
# .env
HF_MODEL=google/gemma-2-2b-it     # or Llama-3, Mistral, Qwen, etc.
HF_TOKEN=hf_xxxx                   # for gated models
```

## Switch to a real dataset

Option A — HF dataset id:
```ini
HF_DATASET=tatsu-lab/alpaca
```
(The `train.py` uses column `text` by default. Alpaca uses `instruction`
+ `output`. Add a preprocessing step in `_load_dataset()` to produce a
`text` column.)

Option B — local JSONL:
```ini
HF_DATASET=/data/my-dataset.jsonl
```
JSONL lines must each be `{"text": "..."}`.

## Tune LoRA aggressiveness

| Goal                        | Settings                           |
|-----------------------------|-----------------------------------|
| Very cheap, quick           | `r=4 alpha=8`                     |
| Standard (recommended)      | `r=8 alpha=16`                    |
| Stronger adaptation         | `r=16 alpha=32`                   |
| Near-full finetune feel     | `r=32 alpha=64`                   |

`alpha` is usually `2*r`; `dropout=0.05` is a fine default.

## Add evaluation

Add a held-out dataset split and evaluate per epoch:

```python
from datasets import load_dataset
ds = load_dataset("tatsu-lab/alpaca", split={"train": "train[:95%]", "eval": "train[95%:]"})
# pass eval_dataset to Trainer, set eval_strategy="epoch"
```

## Full finetune (no LoRA)

Drop the LoRA wrapping:
```python
# remove these lines in train.py:
# lora_cfg = LoraConfig(...)
# model = get_peft_model(model, lora_cfg)
```
Full finetune is much more memory-heavy — needs A100 at minimum. See
`21-distributed-finetune` for the proper multi-GPU setup.

## What NOT to change

- Env-var names: `HF_MODEL`, `HF_DATASET`, `LORA_R`, etc.
- The `run()` return shape (`adapter_dir`, `base_model`, ...). The
  combination templates use this.
- Adapter-dir layout — `peft`/`transformers` convention.
