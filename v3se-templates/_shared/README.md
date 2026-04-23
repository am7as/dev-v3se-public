# `_shared/` — reusable infrastructure

Every template pulls from here. Templates reference these files directly
(via relative paths when cloned into a sibling location of `_shared/`) or
copy-and-adapt when they need a variation.

## What's in here (Phase A minimum)

```
_shared/
├── apptainer/
│   └── base.def               Pixi + Python 3.12 base image
├── docker/
│   └── Dockerfile.dev         Laptop-dev container (matches base.def choices)
├── slurm/
│   ├── cpu.sbatch             CPU-only job, 30 min, 4 CPU, 16 GB RAM
│   └── gpu-t4.sbatch          1× T4 smoke, 10 min
├── scripts/
│   ├── sync-to-cephyr.sh      rsync to vera2 with sensible excludes
│   └── port-forward.sh        tunnel a port from a compute node to laptop
└── env/
    └── .env.template           canonical env-file layout
```

## Deferred (added when a consumer template needs them)

- `apptainer/vllm.def` — added by template `11-multi-provider-inference`.
- `slurm/gpu-a100.sbatch`, `slurm/vllm-server.sbatch` — added by `13`, `21`.
- `scripts/fetch-hf-model.sh`, `scripts/sync-from-cephyr.sh` — added by `03`, `04`.

## Design rules

1. **No template imports from another template.** Cross-template sharing
   is through `_shared/` only.
2. **Env-var contracts are stable.** If you change the meaning of
   `DATA_DIR`, `RESULTS_DIR`, `CEPHYR_USER`, etc., you break every
   template. Don't.
3. **Scripts are self-contained bash.** No Python dependencies for
   scripts that run *before* the container is built.
4. **sbatch scripts are templates.** They live in `_shared/slurm/` for
   copying; each real template has a `slurm/` folder with customized
   copies pointing at its specific entrypoint.
