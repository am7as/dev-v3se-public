# Modification — `21-distributed-finetune`

## Change dataset schema

Rewrite `_format_row()` in `src/dist_ft/train.py`. TRL's SFTTrainer
expects a single `text` column; whatever mapping you apply produces that.

Common shapes:
- Alpaca: `instruction` + `input` + `output`
- ShareGPT: `conversations` list of `{from, value}`
- Chatlogs: `messages` list of `{role, content}`

For chat templates, use the tokenizer's built-in format:
```python
tokenizer.apply_chat_template(row["messages"], tokenize=False)
```

## Resume from checkpoint

```bash
# In the sbatch, change pixi run train to include:
accelerate launch --config_file configs/accelerate/ds_zero2.yaml \
    scripts/train.py --resume_from_checkpoint /cephyr/.../checkpoint-500
```

(SFTTrainer respects the env's `--resume_from_checkpoint` arg; add it
to `scripts/train.py`'s argparse.)

## Multi-node (8× A100 spread over 2 nodes)

Alvis has a max of 4 A100s per node. For 8, request 2 nodes:

```bash
#SBATCH --nodes=2
#SBATCH --gpus-per-node=A100:4
#SBATCH --ntasks-per-node=4
```

Change accelerate config: `num_machines: 2`, `num_processes: 8`, and
use `accelerate launch --machine_rank $SLURM_NODEID ...` inside a
wrapper per node. This is advanced; see C3SE multi-node docs.

## Mix LoRA + distributed

Replace the full-param base model load with PEFT wrapping (copied from
`05-train-lora`), and keep the `accelerate launch` invocation. You get
distributed LoRA — fewer trainable params, same DDP setup.

## What NOT to change

- `configs/accelerate/*.yaml` unless you've read the accelerate +
  DeepSpeed docs. Bad configs produce silent correctness bugs (esp.
  on ZeRO-3 + gradient checkpointing).
- Container paths.
- The `pixi run train` → `accelerate launch` wrapping.
