# Setup — `03-hf-shared-hub`

First-time, one-off preparation. For the zero-to-results flow, read
[`usage.md`](usage.md) — this file only covers prerequisites and the
things you configure once per laptop / cluster account.

This example is **cluster-oriented**. It loads HuggingFace models
exclusively from C3SE's pre-downloaded mirror at
`/mimer/NOBACKUP/Datasets/LLM/huggingface/hub/`. There is no Hub
fallback — if your model isn't mirrored, you must either ask C3SE to
add it or switch to `../08-hf-sif-bundle/` (bake your own SIF) or
`../09-hf-hub-streaming/` (download on demand).

## 1. Host prerequisites (laptop)

| Tool | Minimum | Notes |
|------|---------|-------|
| Docker Desktop (Windows / macOS) or Docker Engine (Linux) | 24.x | only needed for the laptop dev loop (`docker compose up dev`) |
| `git` | 2.30+ | |
| OpenSSH client | any recent | `ssh` + `rsync` |
| Apptainer | optional | unnecessary for this example — all SIFs are built on Alvis |

You do **not** need Apptainer locally for `03-hf-shared-hub`. The
shared-hub path (`/mimer/...`) only exists inside the cluster, so
there is no realistic local-SIF workflow.

## 2. C3SE account prerequisites

- Active Chalmers / SNIC CID.
- NAISS project with Alvis GPU allocation (the `<PROJECT_ID>` you
  paste into sbatch `--account=` lines).
- Cephyr home quota visible under `/cephyr/users/<cid>/`.
- Membership in a Mimer project group (`/mimer/NOBACKUP/groups/<naiss-id>/`).
- SSH public key registered on `alvis2.c3se.chalmers.se` (once per
  laptop; see SUPR).

Quick sanity check from laptop:

**PowerShell:**

```powershell
ssh <cid>@alvis2.c3se.chalmers.se "whoami; C3SE_quota"
```

**bash / zsh:**

```bash
ssh <cid>@alvis2.c3se.chalmers.se "whoami; C3SE_quota"
```

You should see your CID and a quota report. If either fails, fix SSH
access before continuing.

## 3. SSH config

Add to `~/.ssh/config` on laptop. The `ControlMaster` block is
important — it keeps a single TCP session alive so you don't hit the
Chalmers MFA prompt on every `scp` / `rsync`.

```sshconfig
Host alvis
    HostName       alvis2.c3se.chalmers.se
    User           <cid>
    ForwardAgent   yes
    ControlMaster  auto
    ControlPath    ~/.ssh/cm-%r@%h:%p
    ControlPersist 10m

Host cephyr-transfer
    HostName       vera2.c3se.chalmers.se
    User           <cid>
    ControlMaster  auto
    ControlPath    ~/.ssh/cm-%r@%h:%p
    ControlPersist 10m
```

`vera2` is the dedicated transfer node — use it for big `rsync` /
`scp` of results; never use `alvis2` for bulk data movement.

## 4. Cephyr + Mimer workspace layout

Cephyr holds **code only** (capped at 30 GiB / 60 000 files). Mimer
holds **data, weights, apptainer cache, and results**. Create both
on first login:

```bash
ssh alvis
# code root
mkdir -p /cephyr/users/<cid>/Alvis
# per-project code dir (the clone target)
mkdir -p /cephyr/users/<cid>/Alvis/<project>

# Mimer: data + cache + results
mkdir -p /mimer/NOBACKUP/groups/<naiss-id>/<cid>/<project>/{data,results,apptainer-cache}
```

Confirm the mirror itself is visible:

```bash
ls /mimer/NOBACKUP/Datasets/LLM/huggingface/hub/ | head
# Expect: models--google--gemma-2-2b-it, models--meta-llama--..., etc.
```

If `ls` returns empty or permission-denied, stop — your group
membership isn't propagated yet. Email C3SE support.

## 5. First-time `.env`

Copy the template once per clone. Concrete values and the edit list
live in [`usage.md`](usage.md) §4. The vars that are **example-specific**
for `03-hf-shared-hub`:

| Var | Where it comes from |
|-----|---------------------|
| `HF_MODEL_SNAPSHOT` | absolute path under `/mimer/NOBACKUP/Datasets/LLM/huggingface/hub/models--<org>--<name>/snapshots/<hash>/` |
| `HF_DEVICE` | `auto` (recommended) / `cuda` / `cpu` |
| `HF_DTYPE` | `auto` (recommended) / `bfloat16` / `float16` / `float32` |
| `HF_MAX_NEW_TOKENS` | integer, default `256` |

Never commit `.env` — it's listed in `.gitignore`. Propagate it to
the cluster with `scp`, not via git.

### If your model isn't mirrored

`HF_MODEL_SNAPSHOT` has **no fallback**. Before committing to this
example:

```bash
ssh alvis
ls /mimer/NOBACKUP/Datasets/LLM/huggingface/hub/ | grep -i <your-model>
```

If nothing matches, pick a different example:

- `../08-hf-sif-bundle/` — bake weights once, run forever.
- `../09-hf-hub-streaming/` — download at first run into `HF_HOME`
  (consumes Mimer, not Cephyr).

## 6. Quick verification

Five one-liners that should all succeed before you invest time in
`usage.md`:

```bash
ssh alvis C3SE_quota                                              # 1
ssh alvis "ls /mimer/NOBACKUP/groups/<naiss-id>/"                 # 2
ssh alvis "ls /mimer/NOBACKUP/Datasets/LLM/huggingface/hub/ | wc -l"  # 3
ssh alvis "module avail apptainer 2>&1 | head -5"                 # 4
ssh alvis "sbatch --help >/dev/null && echo OK"                   # 5
```

1. You can run commands.
2. Your group dir is visible and writable.
3. The mirror has models (a non-zero count).
4. Apptainer is loadable.
5. Slurm responds.

Once all five are green, proceed to [`usage.md`](usage.md).
