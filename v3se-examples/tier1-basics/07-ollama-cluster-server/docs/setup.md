# Setup — `07-ollama-cluster-server`

First-time setup from fresh clone to a server you can call over SSH
port-forward. Two halves: the **laptop** side (code + dev container +
tunnel), and the **Alvis** side (SIF build + sbatch + Mimer model cache).

## Part A — Laptop prerequisites

### Core tools

- Docker Desktop (Windows / macOS) or Docker Engine (Linux).
- `git`.
- SSH client with `ControlMaster` support (stock OpenSSH is fine).

### Optional: local-only variant

If you just want to run Ollama on your laptop and skip the cluster
entirely, install Ollama from <https://ollama.com/download>. Start
it (`ollama serve` runs as a background service on macOS / Windows,
or as a systemd unit on Linux) and `ollama pull llama3.1:8b` — then
follow only the "Local-only variant" section of [usage.md](usage.md).
Nothing in Part B below applies in that path.

Skip Ollama on your laptop if you only plan to use the cluster-hosted
server; the laptop never runs `ollama` in that path.

## Part B — C3SE Alvis prerequisites

- Alvis allocation with a NAISS project ID (e.g. `NAISS2024-5-123`).
- Your CID has SSH access to `alvis2.c3se.chalmers.se`.
- Cephyr quota headroom (SIF + logs are small) + tens of GiB on Mimer
  for the Ollama model blobs.

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
two shells you'll use (one for the tunnel, one for inspecting host:port),
so you don't re-auth each time.

```sshconfig
Host alvis
    HostName        alvis2.c3se.chalmers.se
    User            <cid>
    IdentityFile    ~/.ssh/id_ed25519_c3se
    ControlMaster   auto
    ControlPath     ~/.ssh/cm-%r@%h:%p
    ControlPersist  10m

Host cephyr-transfer
    HostName        vera2.c3se.chalmers.se
    User            <cid>
    IdentityFile    ~/.ssh/id_ed25519_c3se
    ControlMaster   auto
    ControlPath     ~/.ssh/cm-%r@%h:%p
    ControlPersist  10m
```

Test:

```bash
ssh alvis hostname
ssh cephyr-transfer hostname
```

## Part D — Cephyr + Mimer workspaces

On Alvis, create the code dir on Cephyr and the model cache on Mimer:

```bash
ssh alvis
mkdir -p /cephyr/users/<cid>/Alvis/my-ollama
mkdir -p "$MIMER_GROUP_PATH/<cid>/ollama/models"         # model cache
mkdir -p "$MIMER_GROUP_PATH/<cid>/apptainer-cache"       # SIF build cache
```

Replace `$MIMER_GROUP_PATH` with the concrete path
`/mimer/NOBACKUP/groups/<naiss-id>`. The `ollama/models` dir is what
`OLLAMA_MODELS` will point at; each model is 2–40 GiB across hundreds
to thousands of blob files — **do not** let this land on Cephyr.

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
CEPHYR_PROJECT_PATH=/cephyr/users/<cid>/Alvis/my-ollama
MIMER_GROUP_PATH=/mimer/NOBACKUP/groups/<naiss-id>
MIMER_PROJECT_PATH=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/my-ollama
ALVIS_ACCOUNT=<naiss-id>

OLLAMA_MODEL=llama3.1:8b
OLLAMA_MODELS=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/ollama/models
OLLAMA_PORT=11434
```

`OPENAI_BASE_URL` is left blank — the client reads `results/ollama-host.txt`
and `ollama-port.txt` once the job is running. You'll set
`OPENAI_BASE_URL` explicitly only during the port-forward step.

## Part F — Verify SSH + quota

Before the first SIF build, confirm you have headroom:

```bash
ssh alvis
C3SE_quota                # Cephyr bytes + file count
df -h /mimer/NOBACKUP/groups/<naiss-id>
```

If Cephyr is near its 30 GiB / 60 000-file cap, move existing
caches off before continuing.

## Done

Next: [usage.md](usage.md) for the end-to-end walk from `sbatch` to
a first reply over the tunnel.
