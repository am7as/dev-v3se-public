# Setup — `08-hf-sif-bundle`

First-time, one-off preparation. For the zero-to-results flow, read
[`usage.md`](usage.md) — this file only covers prerequisites and the
things you configure once per laptop / cluster account.

The distinguishing workflow here is
`apptainer build --build-arg HF_MODEL=<repo>` producing a single
`model.sif` file with HuggingFace weights baked in. That SIF is then
portable across laptop and cluster.

## 1. Host prerequisites (laptop)

| Tool | Minimum | Notes |
|------|---------|-------|
| Docker Desktop (Windows / macOS) or Docker Engine (Linux) | 24.x | for the editable dev loop (`docker compose up dev`) |
| `git` | 2.30+ | |
| OpenSSH client | any recent | `ssh` + `scp` + `rsync` |
| Apptainer | 1.2+ | **required** if you want to build `model.sif` locally |
| Disk | ≥ 2× model size | during build, the cache is roughly 2–3× the final SIF |

### Apptainer availability per OS

| OS | Path |
|----|------|
| Linux (Ubuntu, Fedora, Debian, Rocky) | native package — `apt install apptainer` (after enabling the Apptainer PPA) or `dnf install apptainer` |
| Windows | via WSL2 Ubuntu — install Apptainer inside the WSL distribution. Native Windows Apptainer does not exist. |
| macOS (Intel) | via Lima / Apptainer-Desktop or via a Linux VM. Building large SIFs locally is slow — prefer building on Alvis. |
| macOS (Apple Silicon) | same as Intel, but cross-arch builds on arm64 for an x86 base layer are slow. Strongly prefer building on Alvis. |

If you're on macOS and your model is > 4 GiB, skip local builds — do
everything on Alvis's login node where the network and disk are fast.
The `docs/usage.md` § "Option B" path covers this.

## 2. C3SE account prerequisites

- Active Chalmers / SNIC CID.
- NAISS project with Alvis GPU allocation (the `<PROJECT_ID>` you
  paste into sbatch `--account=` lines).
- Cephyr home quota visible under `/cephyr/users/<cid>/`.
- Membership in a Mimer project group (`/mimer/NOBACKUP/groups/<naiss-id>/`).
- SSH public key registered on `alvis2.c3se.chalmers.se`.

Sanity check:

```bash
ssh <cid>@alvis2.c3se.chalmers.se "whoami; C3SE_quota; apptainer --version"
```

## 3. HuggingFace account prerequisites

Required **only** for gated repositories (e.g. the Llama family,
Gemma instruction-tuned variants, Mistral-instruct, some Qwen
variants).

1. Accept the model's license on its HuggingFace page.
2. Generate a **read** token at <https://huggingface.co/settings/tokens>.
3. Store it as `HF_TOKEN=hf_...` in `.env` — never commit `.env`.

For ungated models (`google/gemma-2-2b`, most public small models)
no token is needed; leave `HF_TOKEN=` blank.

## 4. SSH config

Add to `~/.ssh/config`:

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

`vera2` is the dedicated data-transfer node. Big SIF uploads
(multi-GiB model bundles) should go there, never via `alvis2`.

## 5. Cephyr + Mimer workspace layout

Cephyr is for code only (30 GiB / 60 000 files). Mimer is for data,
weights, apptainer cache, results, **and built SIFs**. A baked SIF
often exceeds 4 GiB — keep it on Mimer and symlink into the project
for sbatch convenience.

```bash
ssh alvis

# Code root on Cephyr
mkdir -p /cephyr/users/<cid>/Alvis/<project>

# Mimer: data + cache + results + sifs
mkdir -p /mimer/NOBACKUP/groups/<naiss-id>/<cid>/<project>/{data,results,sifs}
mkdir -p /mimer/NOBACKUP/groups/<naiss-id>/<cid>/apptainer-cache
```

## 6. First-time `.env`

Copy the template once per clone. Concrete values and the edit list
live in [`usage.md`](usage.md) §3. The vars that are **example-specific**
for `08-hf-sif-bundle`:

| Var | Where it comes from |
|-----|---------------------|
| `HF_MODEL` | HuggingFace repo id, e.g. `google/gemma-2-2b-it` |
| `HF_TOKEN` | HF read token for gated models; blank for public |
| `MODEL_DIR` | `/opt/model` — baked path inside the SIF. Don't change unless you also change `apptainer/model.def`. |
| `HF_DEVICE` | `auto` (recommended) / `cuda` / `cpu` |
| `HF_DTYPE` | `auto` / `bfloat16` / `float16` / `float32` |
| `HF_MAX_NEW_TOKENS` | integer, default `256` |

Never commit `.env`. Propagate to cluster with `scp`, not `git`.

## 7. Apptainer cache location (important)

The Apptainer build cache fills fast — a 7 B-parameter model plus
base layers can hit 30 GiB transiently. If the cache lives on Cephyr
(the default `$HOME/.apptainer/`) you WILL blow your quota mid-build.

Set this in your shell rc **and** in any sbatch that builds:

```bash
export APPTAINER_CACHEDIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/apptainer-cache
mkdir -p "$APPTAINER_CACHEDIR"
```

Persist in `~/.bashrc` on Alvis so you never forget:

```bash
ssh alvis 'echo "export APPTAINER_CACHEDIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/apptainer-cache" >> ~/.bashrc'
```

## 8. Quick verification

Six one-liners that should all succeed before the walkthrough:

```bash
# 1 — Alvis reachable, quota healthy
ssh alvis C3SE_quota

# 2 — Apptainer present on cluster
ssh alvis "apptainer --version"

# 3 — APPTAINER_CACHEDIR set and on Mimer
ssh alvis 'echo $APPTAINER_CACHEDIR'

# 4 — Mimer project dir writable
ssh alvis "touch /mimer/NOBACKUP/groups/<naiss-id>/<cid>/.probe && rm /mimer/NOBACKUP/groups/<naiss-id>/<cid>/.probe && echo OK"

# 5 — HF auth works (if HF_TOKEN set; skip otherwise)
curl -fsSL -H "Authorization: Bearer $HF_TOKEN" https://huggingface.co/api/whoami-v2

# 6 — Laptop apptainer (optional; only if building locally)
apptainer --version
```

Once those pass, proceed to [`usage.md`](usage.md).
