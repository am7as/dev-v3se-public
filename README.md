# dev-v3se-public

Public V3SE template library for C3SE clusters (Alvis + Vera).
Three independent deliverables live here, each in its own folder:

| Folder | What it is | When to use it |
|--------|------------|----------------|
| [`v3se-templates/`](v3se-templates/) | Blank single-repo V3SE scaffold (tokenised — instantiate with `scripts/instantiate.{sh,ps1}`). | You're starting a new V3SE project from scratch. |
| [`v3se-examples/`](v3se-examples/) | 15 worked examples across tier-1 / tier-2 / tier-3 (inference, training, multi-source data, pipelines, distributed fine-tuning). | You want a working example to clone and adapt. |
| [`v3se-playbook/`](v3se-playbook/) | Operational docs — storage model (Cephyr vs Mimer), transfer methods, Slurm sbatch patterns, Apptainer recipes. | You need the "how does C3SE actually work" reference. |

Each sub-folder has its own `README.md` that goes into more detail.

## The V3SE conventions

Every template and example in this repo follows the same
non-negotiables, so you can switch between them without re-learning:

- **Apptainer only on Alvis** — Docker is laptop-only.
- **Cephyr = code** (30 GiB + 60k file cap); **Mimer = data / weights / results**.
- `HF_HOME` / `OLLAMA_MODELS` / LM Studio cache **never at `$HOME`** — always Mimer.
- Every `*.sbatch` has `#SBATCH --account=<PROJECT_ID>` (placeholder).
- Container paths are fixed: `/workspace`, `/data`, `/results`, `/models`.
- Env-driven host paths: `${DATA_HOST:-…}` defaults.
- Transfer hosts: `vera2.c3se.chalmers.se` / `alvis2.c3se.chalmers.se`.
- All shell commands shown in both PowerShell and bash/zsh.
- Relative paths + placeholders only (`<cid>`, `<naiss-id>`, `<PROJECT_ID>`).
- No absolute user-home paths anywhere.

## Quick start

```bash
git clone git@github.com:<YOUR_GH_USER>/dev-v3se-public.git
cd dev-v3se-public
```

- Starting clean? → [`v3se-templates/`](v3se-templates/README.md)
- Want a working example? → [`v3se-examples/`](v3se-examples/README.md)
- Need to understand C3SE storage / Slurm / transfers? → [`v3se-playbook/`](v3se-playbook/README.md)

## License

Check each sub-folder's `LICENSE` (if present) for the exact terms.
