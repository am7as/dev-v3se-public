# Transfer, control, and access methods

How you actually move bits between laptop and cluster. Four tools do
all the work, plus four end-to-end workflow patterns — pick the one
that fits.

## The four tools

| Tool   | Purpose                                          | Strengths                                          | Weaknesses                                         |
|--------|--------------------------------------------------|----------------------------------------------------|----------------------------------------------------|
| `ssh`  | **Run commands remotely** and open interactive shells | Works everywhere; one-liner `ssh alvis <cmd>`; ControlMaster reuses connection | Transferring files through `ssh` directly is slow; output only |
| `sshfs`| **Mount remote filesystem as a local folder** | Edit Cephyr / Mimer files in your local editor; no sync step | Slow over high-latency links; IDEs can thrash with indexers; needs FUSE |
| `rsync`| **Differential bulk transfer** | Only moves deltas; handles huge trees well; excludes via patterns | Manual sync step; risk of drift; not version-controlled |
| `git`  | **Version-controlled code transfer** | Proper history; audit trail; integrates with CI; works through firewalls | Not suited for large binaries without LFS; requires a remote; commits even for WIP |

`scp` counts as a degenerate `rsync` — one-shot copy, no delta
smarts. Use for single files or when rsync's overhead isn't worth
it.

## When to use each tool

| Task                                        | Use                                     |
|---------------------------------------------|-----------------------------------------|
| Submit a Slurm job from laptop              | `ssh alvis "cd … && sbatch …"`          |
| Tail a running job's output                 | `ssh alvis "tail -F /cephyr/.../slurm-*.out"` |
| Check queue or quota                        | `ssh alvis squeue -u \$USER` or `ssh alvis C3SE_quota` |
| Edit a single file on cluster without syncing the whole tree | `sshfs` mount, then edit in any editor |
| Push code (versioned, collaborative)        | `git push` → `ssh alvis "cd … && git pull"` |
| Push code (solo, ad-hoc, no remote)         | `rsync` via `sync-to-cephyr.sh`         |
| Push a large dataset                        | `rsync` via `sync-to-mimer.sh`          |
| Push a 10+ GiB `.sif`                       | `scp` one-shot (rsync overhead not worth it for one file) |
| Pull small results                          | `rsync` from Cephyr's `results/`        |
| Pull big checkpoints                        | `rsync` from Mimer                      |
| Watch what's in Cephyr without logging in   | `sshfs` mount + file manager            |

## One-time SSH setup

Make every `ssh`/`rsync`/`scp` command painless:

```
# ~/.ssh/config (same format on Windows PowerShell, macOS, Linux)
Host alvis
  HostName alvis2.c3se.chalmers.se
  User <cid>
  ControlMaster auto
  ControlPath ~/.ssh/control-%r@%h:%p
  ControlPersist yes
  ServerAliveInterval 60
  ServerAliveCountMax 10

Host cephyr-transfer
  HostName vera2.c3se.chalmers.se
  User <cid>
  ControlMaster auto
  ControlPath ~/.ssh/control-%r@%h:%p
  ControlPersist yes
```

Register your public key with C3SE, then `ssh alvis` reuses the same
TCP connection across commands — dramatically faster for scripted
loops.

## Using sshfs (optional)

Lets you browse Cephyr / Mimer as if they were local folders.

**macOS / Linux:**

```bash
sudo apt install sshfs                              # Linux
brew install macfuse sshfs                          # macOS (with Homebrew)

mkdir -p ~/mnt/cephyr ~/mnt/mimer
sshfs alvis:/cephyr/users/<cid>/Alvis  ~/mnt/cephyr
sshfs alvis:/mimer/NOBACKUP/groups/<naiss-id>  ~/mnt/mimer

# Browse with any file manager, edit with any editor.
# Unmount when done:
fusermount -u ~/mnt/cephyr            # Linux
umount ~/mnt/cephyr                   # macOS
```

**Windows (PowerShell):**

Install [WinFsp](https://winfsp.dev/) and [SSHFS-Win](https://github.com/winfsp/sshfs-win),
then:

```powershell
# Map Z: to Cephyr
net use Z: \\sshfs\<cid>@alvis2.c3se.chalmers.se\cephyr\users\<cid>\Alvis
# When done:
net use Z: /delete
```

Caveats: file-manager indexers and IDEs with auto-refresh can hammer
the mount. Don't run VS Code's "Go to Symbol" over a multi-hundred-GB
sshfs mount.

## The four workflow patterns

### (a) Cluster-only

Do all dev directly on the cluster. VS Code Remote-SSH, OnDemand
code-server, or plain terminal on Alvis. No laptop-side code copy.

```
┌────────┐          ┌──────────────────┐
│ laptop │          │ Alvis / Cephyr   │
│ (thin  │ <─SSH──> │   edit + build   │
│  client│          │   + sbatch       │
│  only) │          │   + monitor      │
└────────┘          └──────────────────┘
```

**Pros:** no sync step; one source of truth; editor speaks
directly to the filesystem the jobs see.

**Cons:** no offline work; sluggish when cluster is busy; no
laptop smoke tests; editor session lost on network drop.

### (b) Laptop + auto-sync (rsync)

Edit on laptop, push via rsync, run on cluster.

```
┌────────┐   rsync code      ┌──────────────────┐
│ laptop │ ────────────────> │ Cephyr (code)    │
│ edit + │   rsync data      │                  │
│ smoke  │ ────────────────> │ Mimer (data)     │
│        │ <─── rsync ─────── │ results          │
│        │     ssh sbatch    │                  │
│        │ ────────────────> │ Alvis (compute)  │
└────────┘                   └──────────────────┘
```

**Pros:** full local IDE; offline dev; laptop-side smoke tests.

**Cons:** sync is a manual step; risk of drift; `.pixi/` accidents
possible; no version control on what moved to cluster.

### (c) Laptop + git-sync

Edit on laptop, `git push` to a remote (GitHub / GitLab / internal),
`git pull` on cluster.

```
┌────────┐                  ┌──────────┐                  ┌──────────────────┐
│ laptop │ ── git push ───> │ git host │ <─── git pull ── │ Cephyr           │
│ edit + │                  │ (GitHub, │                  │ cloned repo      │
│ smoke  │                  │  GitLab) │                  │                  │
└────────┘                  └──────────┘                  │ Alvis (compute)  │
                                                         └──────────────────┘
```

**Pros:** real version control; no drift; audit trail; integrates
with team workflow and CI.

**Cons:** needs a remote; commits required for WIP work; large
binaries need git-lfs or sit outside git.

### (d) Hybrid (recommended)

The best of (b) and (c) for most real projects:

```
┌────────┐                     ┌──────────┐
│ laptop │ ─── git push ─────> │ git host │
│ edit   │                     │          │
│ smoke  │ ── rsync DATA ──> Mimer        │
│        │                     │          │
│        │                     v          v
│        │           ┌──────────────────────┐
│        │           │ Alvis login / Cephyr │
│        │ <─ ssh ── │   git pull           │
│        │           │   build SIF          │
│        │           │   sbatch             │
│        │           │   tail -F            │
│        │ <─ rsync ─│   results/           │
│        │           └──────────────────────┘
└────────┘
```

Steps, explicit:

1. **Edit on laptop**.
2. **Smoke test on laptop** in Docker or Apptainer.
3. **`git commit` + `git push`** — code goes to the public remote.
4. **`rsync` any NEW or CHANGED big data** to Mimer (only when data
   actually changed; data rarely changes between runs).
5. **`ssh alvis`** (single persistent connection via ControlMaster).
6. On cluster: **`git pull`** in the project folder on Cephyr.
7. **Build the SIF** (first run only, or after dep changes).
8. **Smoke test on cluster** — `sbatch slurm/cpu-smoke.sbatch` or
   `gpu-t4.sbatch`; verify green before any long run.
9. **`sbatch`** the real job.
10. **Watch** with `ssh alvis "tail -F …"` from laptop.
11. **Pull results back**: small via `rsync` from Cephyr
    `results/`; big via `rsync` from Mimer `checkpoints/` /
    `results/`. Optionally commit small result artefacts back via
    git from laptop.
12. **Control + file access during the run**: always `ssh alvis`.
    File browsing optional via `sshfs`.

### Quick comparison

| Pattern          | Pros                                    | Cons                                     | Best for                                  |
|------------------|-----------------------------------------|------------------------------------------|-------------------------------------------|
| (a) cluster-only | No sync step                            | No offline work; editor feels remote     | Short ad-hoc cluster tweaks               |
| (b) rsync        | Full local IDE; no git overhead         | Manual sync; no version control          | Solo, pre-git, ad-hoc prototyping         |
| (c) git          | Version-controlled; team-friendly       | Commits for WIP; needs remote            | Teams, long-lived projects                |
| **(d) hybrid**   | **Version control + fast data sync + local smoke** | Slightly more moving parts | **Most real projects — the recommended default** |

## Pulling it together: a single session in pattern (d)

```bash
# ---- on laptop ----
git commit -am "tweak eval threshold"
git push                                             # to public remote
bash ./_shared/scripts/sync-to-mimer.sh ./new-splits # if data changed

ssh alvis                                            # persistent via ControlMaster
```

Inside the `ssh alvis` session (reused across commands below):

```bash
cd /cephyr/users/<cid>/Alvis/<project>
git pull                                             # ← not rsync
apptainer build -F dev.sif apptainer/dev.def        # rebuild only if deps changed
sbatch slurm/cpu-smoke.sbatch                        # fast smoke first
tail -F slurm-*.out                                  # ctrl-C when green
sbatch slurm/gpu-a100.sbatch                         # the real job
```

Back on laptop (another terminal or after `ssh` disconnect):

```bash
rsync -avh --progress \
  <cid>@vera2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/<project>/results/ \
  ./results/

rsync -avh --progress \
  <cid>@vera2.c3se.chalmers.se:/mimer/NOBACKUP/groups/<naiss-id>/<cid>/<project>/checkpoints/ \
  ./checkpoints/

git add results/summary.json && git commit -m "run 2026-04-21" && git push
```

One commit per experiment; full reproducibility; no rsync drift.
