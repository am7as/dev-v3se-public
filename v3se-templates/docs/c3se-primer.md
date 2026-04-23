# C3SE primer — Alvis, Cephyr, and Mimer in 10 minutes

The facts you need before cloning any template. Sourced from C3SE's
official docs (cited inline).

## The three moving parts

| System | Role       | Path / host                                    | Size            | Backed up? |
|--------|-----------|------------------------------------------------|-----------------|:----------:|
| **Alvis**  | GPU compute | `alvis1.c3se.chalmers.se`, `alvis2.c3se.chalmers.se` | —         | —          |
| **Cephyr** | small personal storage | `/cephyr/users/<cid>/Alvis/` (your home)  | **30 GiB / 60k files** | yes        |
| **Mimer**  | large project storage  | `/mimer/NOBACKUP/groups/<naiss-id>/`       | **per-project allocation** (e.g. 800 GiB) | no         |

**Key idea**: Cephyr is for *code and configs*; Mimer is for *data,
model weights, results*. Both are automatically visible from Alvis
compute nodes (auto-bind into Apptainer containers).

There's also read-only shared content:

- `/mimer/NOBACKUP/Datasets/` — read-only shared datasets (vision/NLP).
- `/mimer/NOBACKUP/Datasets/LLM/huggingface/hub/` — pre-downloaded HF
  models, read-only.
- `/apps/` — system-wide Apptainer images and modules, read-only.

Sources:
<https://www.c3se.chalmers.se/documentation/file_transfer/filesystem/>
<https://www.c3se.chalmers.se/documentation/alvis/mimer/>

## Quotas that will bite you

### Cephyr (your home, strict quota)

- **30 GiB** of bytes.
- **60,000 files** (inode count).
- Hit either → job crashes silently (file-creation failures).
- Check anytime: `C3SE_quota`.
- **Implication**: models go into SIF images (one file), not unpacked
  trees. See [sif-management.md](sif-management.md).

### Mimer (project allocation, data / weights / results)

- Allocated per-project in units of GiB (e.g. `800 GiB` for a typical
  allocation). Usage reported in the NAISS portal:
  ```
  Mimer @ C3SE
  /mimer/NOBACKUP/groups/naiss0000-0-000    800    GiB    …    % used …   <last-updated>
  ```
- No backups — keep originals somewhere else.
- **Implication**: anything big (datasets, checkpoints, logs, unpacked
  HF models, tensorboard events, wandb runs) lives here, not on
  Cephyr.

### Alvis (compute allocation)

- Allocated per-project in GPU-hours/month (e.g. `500 GPU-h/month`).
- Check usage in the NAISS portal.
- Idle GPUs are flagged — always `--gpus-per-node=…` the number you'll
  actually use.

## Connecting

```bash
ssh <cid>@alvis1.c3se.chalmers.se     # login node (interactive, not for heavy work)
ssh <cid>@alvis2.c3se.chalmers.se     # also login
ssh <cid>@vera2.c3se.chalmers.se      # transfer node — use for rsync/scp
```

**Open OnDemand portal** (browser-based): Jupyter, VS Code, file manager,
remote graphics. Best entry point for most researchers. See
<https://www.c3se.chalmers.se/documentation/connecting/ondemand/>.

SSH config tip — avoid re-authenticating every command:
```
# ~/.ssh/config
Host alvis
  HostName alvis2.c3se.chalmers.se
  User <cid>
  ControlMaster auto
  ControlPath ~/.ssh/control-%r@%h:%p
  ControlPersist yes
```

## Containers

**Apptainer only** on Alvis — no Docker. Root-less, security-friendly,
runs from a single `.sif` file. **The same SIF file runs on laptop and
on the cluster** — one build artefact, two execution targets. Docker
is laptop-only.

- Build on login node or laptop:
  ```bash
  apptainer build my.sif my.def
  ```
- Run, auto-mounting cwd + home + /cephyr + /mimer + /apps:
  ```bash
  apptainer run --nv my.sif            # --nv exposes GPUs
  ```
- Extra bind mounts:
  ```bash
  apptainer run --bind /mimer/NOBACKUP/groups/<naiss-id>/data:/data my.sif
  ```

Source: <https://www.c3se.chalmers.se/documentation/miscellaneous/containers/>

## GPUs

```bash
#SBATCH --gpus-per-node=T4:1         # 1× Tesla T4 (smoke tests)
#SBATCH --gpus-per-node=A100:1       # 1× A100 (real work)
#SBATCH --gpus-per-node=A100:4       # 4× A100 (distributed)
```

**You must use every GPU you allocate** — C3SE will flag idle GPUs.
Always test with T4 first.

Source: <https://www.c3se.chalmers.se/documentation/submitting_jobs/running_jobs/>

## Python on Alvis: the DOs and DON'Ts

- **DO** run Python inside an Apptainer container — the cleanest way
  to control file count and deps.
- **DO** point `HF_HOME`, `TORCH_HOME`, `PIP_CACHE_DIR` at Mimer
  (`/mimer/NOBACKUP/groups/<naiss-id>/<user>/…`) — big caches don't
  belong on Cephyr.
- **DON'T** use Miniconda in `$HOME` — explodes the Cephyr file count.
- **DON'T** let `pip install --user` write to `~/.local/` for the same
  reason.

Source: <https://www.c3se.chalmers.se/documentation/module_system/python/>

## LLMs on Alvis

Three supported patterns for running LLMs on Alvis:

1. **vLLM via Apptainer + Slurm** — preferred for serving open-weight
   models. Launch a server on a GPU node, port-forward to your laptop.
   Source: <https://www.c3se.chalmers.se/documentation/software/machine_learning/vllm/>
2. **LM Studio / Ollama via Apptainer + Slurm** — also supported;
   port-forward pattern identical to vLLM. Use project-scoped
   `OLLAMA_MODELS` / LM Studio cache under Mimer (never `~/.ollama/`
   or `~/.lmstudio/` — Cephyr quota).
3. **HuggingFace in-process** — `transformers.AutoModel.from_pretrained()`
   directly. Prefer pre-downloaded snapshots at
   `/mimer/NOBACKUP/Datasets/LLM/huggingface/hub/` when available.

Closed-model token APIs (OpenAI, Anthropic, Google, xAI) work from
compute nodes over outbound HTTPS — but calling them from a GPU sbatch
wastes your allocation. Fire from the login node or a CPU-only sbatch.

## File transfer

### Code to Cephyr

```bash
rsync -avh --progress ./my-project/ <cid>@vera2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/my-project/
```

### Data / weights / large results to Mimer

```bash
rsync -avh --progress ./my-data/ <cid>@vera2.c3se.chalmers.se:/mimer/NOBACKUP/groups/<naiss-id>/my-data/
```

### Bringing things back

```bash
# small results on Cephyr:
rsync -avh --progress <cid>@vera2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/my-project/results/ ./results/

# bulk results / trained weights on Mimer:
rsync -avh --progress <cid>@vera2.c3se.chalmers.se:/mimer/NOBACKUP/groups/<naiss-id>/my-project/checkpoints/ ./checkpoints/
```

Bulk transfers (> 100 GB): see
<https://www.c3se.chalmers.se/documentation/file_transfer/bulk_data_transfer/>.

## When something fails on Alvis — checklist

1. `C3SE_quota` — did you hit Cephyr's 30 GiB / 60k-file cap?
2. Mimer usage in the NAISS portal — did you hit the project allocation?
3. `squeue -u $USER` — is your job even running?
4. Check the job's `.out` / `.err` files — usually in the job-submit dir.
5. `sacct -j <jobid> --format=JobID,State,ExitCode,Elapsed,MaxRSS` —
   exit code and memory.
6. Was `--nv` passed to Apptainer? Missing `--nv` = no GPU visibility.
7. Was `HF_HOME` pointing at Mimer project storage, not `$HOME` or
   Cephyr? Same for `OLLAMA_MODELS`, LM Studio's model dir.

## Resources worth bookmarking

- First-time users: <https://www.c3se.chalmers.se/documentation/first_time_users/>
- Alvis intro slides: <https://www.c3se.chalmers.se/documentation/first_time_users/intro-alvis/slides/>
- Mimer project storage: <https://www.c3se.chalmers.se/documentation/alvis/mimer/>
- Software catalog: <https://www.c3se.chalmers.se/documentation/software/>
- All C3SE docs: <https://www.c3se.chalmers.se/documentation/>
