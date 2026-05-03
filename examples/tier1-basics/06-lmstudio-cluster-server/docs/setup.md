# Setup — `06-lmstudio-cluster-server`

First-time setup from a fresh clone to a server you can call over SSH
port-forward. Two halves: the **laptop** side (code + dev container +
tunnel), and the **Alvis** side (SIF build + sbatch + Mimer model cache).

## Part A — Laptop prerequisites

### Core tools

- Docker Desktop (Windows / macOS) or Docker Engine (Linux).
- `git`.
- SSH client with `ControlMaster` support (stock OpenSSH is fine).

### Optional: local-only variant

If you just want to run LM Studio on your laptop and skip the cluster
entirely, install the LM Studio GUI from <https://lmstudio.ai>.
Load a model, start its server on port `1234`, and you can follow only
section "Local-only variant" in [usage.md](usage.md) — nothing below
section Part B applies.

Skip LM Studio install on your laptop if you only plan to use the
cluster-hosted server; the laptop never runs `lms` in that path.

## Part B — C3SE Alvis prerequisites

- Alvis allocation with a NAISS project ID (e.g. `NAISS2024-5-123`).
- Your CID (Chalmers ID) has SSH access to `alvis2.c3se.chalmers.se`.
- At least a few GiB of Cephyr quota free (SIF + logs), and a
  several-tens-of-GiB slice of Mimer for the LM Studio model cache.

### SSH key

Generate a key on the laptop if you don't already have one:

**PowerShell:**

```powershell
ssh-keygen -t ed25519 -f $HOME\.ssh\id_ed25519_c3se
```

**bash / zsh:**

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_c3se
```

Upload the `.pub` to C3SE via SUPR / Alvis portal.

## Part C — SSH config

Add two hosts to `~/.ssh/config` (create the file if missing). The
`ControlMaster` entries keep a single TCP connection open across the
two shells you'll use (one for the tunnel, one to read host:port), so
you don't re-auth mid-session.

```sshconfig
Host alvis
    HostName        alvis2.c3se.chalmers.se
    User            <cid>
    IdentityFile    ~/.ssh/id_ed25519_c3se
    ControlMaster   auto
    ControlPath     ~/.ssh/cm-%r@%h:%p
    ControlPersist  10m

Host cephyr-transfer
    HostName        alvis2.c3se.chalmers.se
    User            <cid>
    IdentityFile    ~/.ssh/id_ed25519_c3se
    ControlMaster   auto
    ControlPath     ~/.ssh/cm-%r@%h:%p
    ControlPersist  10m
```

Test:

```bash
ssh alvis hostname    # should print an alvis login host
ssh cephyr-transfer hostname
```

## Part D — Cephyr + Mimer workspaces

On Alvis, create the code dir on Cephyr and the model cache on Mimer:

```bash
ssh alvis
mkdir -p /cephyr/users/<cid>/Alvis/my-lmstudio
mkdir -p "$MIMER_GROUP_ROOT/<cid>/lmstudio"           # model cache
mkdir -p "$MIMER_GROUP_ROOT/<cid>/apptainer-cache"    # SIF build cache
```

Replace `$MIMER_GROUP_ROOT` with your concrete path (it's
`/mimer/NOBACKUP/groups/<naiss-id>`). The `lmstudio` dir is what
`LMSTUDIO_CACHE_DIR` will point at; LM Studio drops 10+ GiB model
archives here across thousands of files — never let this path land on
Cephyr.

## Part E — Copy .env and fill in placeholders

**PowerShell:**

```powershell
Copy-Item .env.example .env
notepad .env
```

**bash / zsh:**

```bash
cp .env.example .env
${EDITOR:-vi} .env
```

Fill in at minimum:

```ini
CEPHYR_USER=<cid>
CEPHYR_PROJECT_DIR=/cephyr/users/<cid>/Alvis/my-lmstudio
MIMER_GROUP_ROOT=/mimer/NOBACKUP/groups/<naiss-id>
MIMER_USER_DIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-lmstudio
ALVIS_ACCOUNT=<naiss-id>

LMSTUDIO_MODEL=lmstudio-community/llama-3.1-8b-instruct
LMSTUDIO_CACHE_DIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/lmstudio
```

`OPENAI_BASE_URL` is left blank — the client reads `results/lmstudio-host.txt`
and `lmstudio-port.txt` once the job is running. You'll only set
`OPENAI_BASE_URL` manually during the port-forward step (see usage).

## Part F — Verify SSH + quota

Before the first SIF build, confirm you have elbow room:

```bash
ssh alvis
C3SE_quota                # Cephyr bytes + file count
df -h /mimer/NOBACKUP/groups/<naiss-id>
```

If Cephyr is near its 30 GiB / 60 000-file cap, move existing
caches (`~/.cache`, old `.pixi/`) off before continuing.

## Done

Next: [usage.md](usage.md) for the end-to-end walk from `sbatch` to
a first reply over the tunnel.
