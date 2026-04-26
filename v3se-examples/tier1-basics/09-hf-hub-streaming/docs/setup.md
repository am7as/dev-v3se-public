# Setup — `09-hf-hub-streaming`

First-time, one-off preparation. For the zero-to-results flow, read
[`usage.md`](usage.md) — this file only covers prerequisites and the
things you configure once per laptop / cluster account.

This example **streams the model from the HuggingFace Hub** into
`HF_HOME` on first call and reuses the cache thereafter. The one
critical decision that keeps this template safe on Alvis is where
`HF_HOME` lives: never under `$HOME` or `/cephyr/`.

## 1. Host prerequisites (laptop)

| Tool | Minimum | Notes |
|------|---------|-------|
| Docker Desktop (Windows / macOS) or Docker Engine (Linux) | 24.x | used by the `dev` service in `docker-compose.yml` |
| `git` | 2.30+ | |
| OpenSSH client | any recent | `ssh`, `scp`, `rsync` |
| Apptainer | optional | only if you want a local SIF build; otherwise build on Alvis |
| Free disk | 10–50 GiB | HF cache ballooning room — `google/gemma-2-2b-it` alone is ~5 GiB |

On Windows prefer running the `bash` snippets from Git-Bash or WSL2.
PowerShell-only snippets are marked as such.

## 2. C3SE account prerequisites

- Active Chalmers / SNIC CID.
- NAISS project with Alvis GPU allocation (the `<PROJECT_ID>` you paste
  into every sbatch `--account=` line).
- Cephyr home quota visible at `/cephyr/users/<cid>/` (30 GiB /
  60 000 files — it is easy to blow this with HF caches if `HF_HOME`
  is misconfigured).
- Membership in a Mimer project group
  (`/mimer/NOBACKUP/groups/<naiss-id>/`). Mimer is where the HF cache
  **must** live.
- SSH public key registered on `alvis2.c3se.chalmers.se`.
- If you plan to stream a **gated** model (Llama, gemma-*-it, …): a
  HuggingFace account with access granted on the model card, plus a
  user token at <https://huggingface.co/settings/tokens> (scope: read).

## 3. SSH config

Add to `~/.ssh/config` on laptop. `ControlMaster` keeps one TCP
session alive so you don't re-MFA on every `scp`.

```sshconfig
Host alvis
    HostName       alvis2.c3se.chalmers.se
    User           <cid>
    ForwardAgent   yes
    ControlMaster  auto
    ControlPath    ~/.ssh/cm-%r@%h:%p
    ControlPersist 10m

Host cephyr-transfer
    HostName       alvis2.c3se.chalmers.se
    User           <cid>
    ControlMaster  auto
    ControlPath    ~/.ssh/cm-%r@%h:%p
    ControlPersist 10m
```

`vera2` is the dedicated transfer node for bulk `rsync` / `scp`
(e.g. pulling `results/`). Never use `alvis2` for bulk transfers.

## 4. Cephyr + Mimer workspace layout

Cephyr = **code only**. Mimer = **everything else**, most importantly
the HF cache for this template.

**bash / zsh (on Alvis):**

```bash
ssh alvis
# Code tree on Cephyr
mkdir -p /cephyr/users/<cid>/Alvis/<project>

# Per-project Mimer tree — notice the dedicated .hf-cache
mkdir -p /mimer/NOBACKUP/groups/<naiss-id>/<cid>/<project>/{data,results,apptainer-cache}
mkdir -p /mimer/NOBACKUP/groups/<naiss-id>/<cid>/<project>/.hf-cache
```

**PowerShell (dispatching commands to Alvis from laptop):**

```powershell
ssh alvis "mkdir -p /cephyr/users/<cid>/Alvis/<project>"
ssh alvis "mkdir -p /mimer/NOBACKUP/groups/<naiss-id>/<cid>/<project>/{data,results,apptainer-cache,.hf-cache}"
```

The `.hf-cache` directory is what `HF_HOME` will point at. It lives on
Mimer so:

- Weights don't count against your 60 000-file Cephyr quota.
- Every compute node on Alvis sees the **same** cache — first run
  downloads, every subsequent run is an instant cache hit.

## 5. Gated-model token (optional)

Skip this section if you're only using public models (Gemma base,
Qwen, Phi, ...). For gated families:

```bash
# on laptop
export HF_TOKEN=hf_xxx
```

Later you'll paste the same value into `.env` (never commit it).

Verify access before depending on it:

```bash
curl -sH "Authorization: Bearer $HF_TOKEN" \
  https://huggingface.co/api/models/<org>/<model> | head -c 200
```

A JSON blob with the model metadata = OK. `401` / `403` = you haven't
accepted the licence on the model card.

## 6. First-time `.env`

Copy the template once per clone. Concrete values live in
[`usage.md`](usage.md) §3. The vars that are **example-specific** for
`09-hf-hub-streaming`:

| Var | Purpose |
|-----|---------|
| `HF_MODEL` | HuggingFace repo id, e.g. `google/gemma-2-2b-it` |
| `HF_HOME` | cache root — `/workspace/.hf-cache` on laptop, `/mimer/.../.hf-cache` on cluster |
| `TRANSFORMERS_CACHE` | same as `HF_HOME` — some transformers versions still read this |
| `HF_TOKEN` | only set for gated models |
| `HF_DEVICE` | `auto` / `cuda` / `cpu` |
| `HF_DTYPE` | `auto` / `bfloat16` / `float16` / `float32` |
| `HF_MAX_NEW_TOKENS` | integer, default `256` |

Never commit `.env` — it's listed in `.gitignore`. The laptop and
cluster copies of `.env` should differ in `HF_HOME` only.

## 7. Quick verification

Five one-liners that should all succeed before you invest time in
`usage.md`:

```bash
ssh alvis C3SE_quota                                                 # 1
ssh alvis "ls -d /mimer/NOBACKUP/groups/<naiss-id>/<cid>/"           # 2
ssh alvis "mkdir -p \$MIMER_PROJECT_PATH/.hf-cache && ls -d \$_"     # 3
ssh alvis "module avail apptainer 2>&1 | head -5"                    # 4
ssh alvis "sbatch --help >/dev/null && echo OK"                      # 5
```

1. You can run commands on Alvis.
2. Your group dir is visible.
3. The HF cache dir on Mimer exists and is writable.
4. Apptainer is loadable.
5. Slurm responds.

Once all five are green, proceed to [`usage.md`](usage.md).
