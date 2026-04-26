# Setup — `14-git-model-bundle`

First-time, one-off preparation. For the zero-to-results flow, read
[`usage.md`](usage.md) — this file only covers prerequisites and the
things you configure once per laptop / cluster account.

This example bakes a **git-hosted model repo** into either a SIF
(for cluster use) or a Docker image (for laptop use). The model
weights live inside the built image at `/opt/model`. There is no
network dependency at run time.

## 1. Host prerequisites (laptop)

| Tool | Minimum | Notes |
|------|---------|-------|
| Docker Desktop (Windows / macOS) or Docker Engine (Linux) | 24.x | needed for `dev` service and `Dockerfile.bundle` build |
| `git` | 2.30+ | |
| `git-lfs` | 3.x | only if the model repo stores weights via LFS |
| OpenSSH client | any recent | `ssh`, `scp`, `rsync` |
| Apptainer | optional, 1.2+ | build the SIF locally (Linux / WSL2 / macOS+macFUSE). Otherwise build on Alvis. |
| Free disk | 2× repo size | one copy while cloning, one copy inside the image |

On Windows we strongly recommend building the SIF on Alvis rather
than under WSL2 — Apptainer's `overlayfs` is finicky on Windows
volumes.

## 2. C3SE account prerequisites

- Active Chalmers / SNIC CID.
- NAISS project with Alvis GPU allocation (the `<PROJECT_ID>` value
  you paste into sbatch `--account=` lines).
- Cephyr home quota visible at `/cephyr/users/<cid>/` (30 GiB /
  60 000 files — **do not** put the SIF here if it's big).
- Membership in a Mimer project group
  (`/mimer/NOBACKUP/groups/<naiss-id>/`). The built SIF lives here.
- SSH public key on `alvis2.c3se.chalmers.se`.
- If the git-hosted model ultimately downloads HuggingFace-gated
  weights during its install step (some research repos do): an HF
  user token with access already granted on the model card.

## 3. SSH config

Add to `~/.ssh/config` on laptop. The `ControlMaster` block keeps
one TCP session alive so you don't re-MFA on every `scp`.

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

Use `cephyr-transfer` when copying the built SIF to/from Mimer.
`scp bundle.sif cephyr-transfer:/mimer/...` — never push multi-gig
files through `alvis2`.

## 4. Auth for the model-repo git host

This is the step that differs from `03` and `09`. You need clone
permissions for `MODEL_REPO` **from whichever host builds the SIF**.

### Public repos

Nothing to do — HTTPS clone works anonymously:

```ini
# .env
MODEL_REPO=https://github.com/<org>/<repo>.git
```

### Private repos — SSH keys (recommended)

Preferred for long-lived auth. On the laptop (or Alvis) build host:

```bash
ssh-keygen -t ed25519 -C "<cid>@<build-host>" -f ~/.ssh/id_model_repo
cat ~/.ssh/id_model_repo.pub
# Paste the .pub contents into your GitHub/GitLab deploy keys (read-only).
```

Test:

```bash
ssh -T git@github.com -i ~/.ssh/id_model_repo
git ls-remote git@github.com:<org>/<repo>.git
```

Use an SSH URL in `.env`:

```ini
MODEL_REPO=git@github.com:<org>/<repo>.git
```

**Important.** If you build the SIF on Alvis, the key must be
present on Alvis too (or use `ssh-agent` forwarding via
`ForwardAgent yes` — see §3).

### Private repos — HTTPS with a PAT

Acceptable for one-off builds on a trusted machine:

```ini
MODEL_REPO=https://<username>:<pat>@github.com/<org>/<repo>.git
```

Warning: the PAT ends up in the shell history and (briefly) in the
SIF build log. Prefer SSH keys.

### LFS

If the repo stores weights via git-lfs:

```bash
git lfs install
git lfs ls-files
```

`apptainer/bundle.def`'s `%post` already runs `git lfs pull || true`.
For repos with > 10 GiB LFS, see `modification.md` §4 — you may want
to pre-download and use `%files` instead of cloning during build.

## 5. Cephyr + Mimer workspace layout

Cephyr = code only. Mimer = built SIF + apptainer cache + results.

**bash / zsh (on Alvis):**

```bash
ssh alvis
# Code tree on Cephyr
mkdir -p /cephyr/users/<cid>/Alvis/<project>

# Per-project Mimer tree
mkdir -p /mimer/NOBACKUP/groups/<naiss-id>/<cid>/<project>/{data,results,sifs,apptainer-cache}
```

**PowerShell (dispatching from laptop):**

```powershell
ssh alvis "mkdir -p /cephyr/users/<cid>/Alvis/<project>"
ssh alvis "mkdir -p /mimer/NOBACKUP/groups/<naiss-id>/<cid>/<project>/{data,results,sifs,apptainer-cache}"
```

The `sifs/` directory is where `bundle.sif` will end up after you
`mv` it off Cephyr. The `apptainer-cache/` directory is where you
point `APPTAINER_CACHEDIR` during large builds (covered in
`usage.md` §3B).

## 6. First-time `.env`

Copy the template once per clone. Values and edit flow live in
[`usage.md`](usage.md) §2. The vars that are **example-specific**
for `14-git-model-bundle`:

| Var | Purpose |
|-----|---------|
| `MODEL_REPO` | git URL of the model repo (HTTPS or SSH) |
| `MODEL_REF` | branch / tag / commit to check out (default `main`) |
| `MODEL_DIR` | **do not change** — path inside the image (`/opt/model`) |
| `HF_TOKEN` | only if the model-repo downloads HF-gated weights during its install |

Never commit `.env` — it's in `.gitignore`. Propagate to cluster
with `scp`, not git.

## 7. Quick verification

Six one-liners that should all succeed before you invest time in
`usage.md`:

```bash
ssh alvis C3SE_quota                                                 # 1
ssh alvis "ls -d /mimer/NOBACKUP/groups/<naiss-id>/<cid>/"           # 2
ssh alvis "module avail apptainer 2>&1 | head -5"                    # 3
ssh alvis "sbatch --help >/dev/null && echo OK"                      # 4
git ls-remote $MODEL_REPO | head -3                                  # 5
docker --version                                                     # 6
```

1. You can run commands on Alvis.
2. Your Mimer group dir is visible.
3. Apptainer is loadable (required for SIF builds on Alvis).
4. Slurm responds.
5. You can clone `$MODEL_REPO` — this is the single most common
   reason SIF builds fail later.
6. Docker works on laptop (needed for the `dev` service and
   `Dockerfile.bundle`).

Once all six are green, proceed to [`usage.md`](usage.md).
