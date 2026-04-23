# Modification — `22-reconstruct-retrain-infer`

## Define your own surgery

Edit `src/reco/surgery.py`. Pattern:

```python
def my_operation(base_model_id: str, out_dir: Path, **kwargs):
    token = os.environ.get("HF_TOKEN") or None
    model = AutoModel.from_pretrained(base_model_id, token=token)
    # ... mutate model here
    model.save_pretrained(str(out_dir))
    return {"operation": "my_operation", ...}
```

Wire it into `run()`:

```python
elif op == "my_operation":
    summary = my_operation(base_model_id=base, out_dir=out_dir, ...)
```

Document the operation in `configs/surgery.yaml`.

## Common surgery recipes

### Freeze everything except a specific layer
```python
for name, p in model.named_parameters():
    if not name.startswith("classifier"):
        p.requires_grad = False
```

### Add a projection before the LM head (for multi-task learning)
```python
from torch import nn
hidden = model.config.hidden_size
model.projection = nn.Linear(hidden, hidden)
# Reroute forward() to go through projection...
```

### Replace attention with a custom module
Subclass the transformer block, override `forward()`, register via
`model.config.model_type`'s map. See HuggingFace "modeling_xxx.py" patterns.

## Loss customization

For regression, change `Trainer` to use `MSELoss` implicitly via
`num_labels=1` + `problem_type="regression"` in the model config. For
multi-label, `problem_type="multi_label_classification"` and BCE loss.
For a fully custom loss, subclass `Trainer`:

```python
class MyTrainer(Trainer):
    def compute_loss(self, model, inputs, return_outputs=False):
        outputs = model(**inputs)
        my_loss = ...
        return (my_loss, outputs) if return_outputs else my_loss
```

## Use DeepSpeed for big reconstructions

Copy an `accelerate/*.yaml` from `21-distributed-finetune/configs/` and
change the pixi task to `accelerate launch --config_file configs/ds_zero2.yaml scripts/train.py`.

## Stream evaluation

Current `evaluate.run()` iterates the test set row-by-row. For big eval
sets, batch it:

```python
from torch.utils.data import DataLoader
loader = DataLoader(ds_tok, batch_size=32, collate_fn=...)
with torch.no_grad():
    for batch in loader:
        out = model(**batch)
        # collect logits
```

## What NOT to change

- The four-stage pipeline names (`surgery`, `train`, `eval`, `bundle`).
- The `/opt/model` convention inside the bundle.
- The surgery-config-as-YAML pattern — makes surgery reproducible.
