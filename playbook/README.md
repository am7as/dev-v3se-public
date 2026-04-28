# playbook

Information-flow playbook for **public / single-repo** projects on
Chalmers C3SE's environment (Alvis GPU compute, Cephyr home
storage, Mimer project storage).

This folder is **documentation only** — it tells you how to move
code, data, and results between your laptop and the cluster. It does
not introduce new code or templates; it explains the plumbing that
sits alongside the scaffolds in
[`../templates/`](../templates/) and
[`../examples/`](../examples/).


## Storage at a glance

| Where                                         | Role                         | Size / quota                     | Backups |
|-----------------------------------------------|------------------------------|----------------------------------|:-------:|
| **Laptop**                                    | edit + build + smoke-test    | your disk                        | yours    |
| **Cephyr** `/cephyr/users/<cid>/Alvis/<proj>/`| code + configs only          | 30 GiB, 60,000 files hard cap    | yes      |
| **Mimer project** `/mimer/NOBACKUP/groups/<naiss-id>/` | data, weights, big results | per-project allocation (e.g. 800 GiB) | no   |
| **Mimer shared** `/mimer/NOBACKUP/Datasets/`  | read-only shared datasets    | —                                | —        |

**Golden rule**: code → Cephyr; everything big → Mimer.

## The end-to-end loop

```
 laptop                           Cephyr                    Alvis             Mimer
┌────────┐                      ┌────────┐              ┌────────┐         ┌────────┐
│ edit   │── rsync code ───────>│ code   │<── autobind──│ sbatch │<──bind──│ data,  │
│ code   │                      │        │              │ job    │         │ models │
│        │<── rsync results ────│ logs   │              │        │──write──│        │
│ data,  │── rsync data   ─────────────────────────────────────────────────>│        │
│ models │<── rsync artefacts ──────────────────────────────────────────────│        │
└────────┘                      └────────┘              └────────┘         └────────┘
```

Each arrow corresponds to a concrete command — see the docs below.

## Commands, dual-platform

Every shell command is shown in both PowerShell (Windows) and
bash/zsh (macOS/Linux). Each project template ships helper scripts
(`_shared/scripts/sync-to-cephyr.sh`, `sync-to-mimer.sh`,
`port-forward.sh`) that wrap the raw commands for you.

| Topic | Doc |
|-------|-----|
| **First-time setup: SSH bootstrap (start here)** | [docs/ssh-bootstrap.md](docs/ssh-bootstrap.md) |
| **Windows-specific gotchas (PS 5.x, OpenSSH, WSL)** | [docs/windows-onboarding.md](docs/windows-onboarding.md) |
| Storage model (what goes where and why) | [docs/storage-model.md](docs/storage-model.md) |
| Transfer tools + 4 workflow patterns (ssh / sshfs / rsync / git) | [docs/transfer-methods.md](docs/transfer-methods.md) |
| Push: code to Cephyr, data to Mimer     | [docs/push-to-cluster.md](docs/push-to-cluster.md) |
| Pull: results + artefacts back          | [docs/pull-from-cluster.md](docs/pull-from-cluster.md) |
| Job lifecycle: sbatch, monitor, debug   | [docs/job-lifecycle.md](docs/job-lifecycle.md) |
| Common gotchas & recovery               | [docs/gotchas.md](docs/gotchas.md) |

## One-time setup (laptop)

Add an SSH config entry so every subsequent command just works:

```
# ~/.ssh/config (same on Windows PowerShell, macOS, Linux)
Host alvis
  HostName alvis2.c3se.chalmers.se
  User <cid>
  ControlMaster auto
  ControlPath ~/.ssh/control-%r@%h:%p
  ControlPersist yes

Host cephyr-transfer
  HostName alvis2.c3se.chalmers.se
  User <cid>
```

Then test:

**PowerShell:**

```powershell
ssh alvis C3SE_quota      # shows your Cephyr usage
```

**bash / zsh:**

```bash
ssh alvis C3SE_quota      # shows your Cephyr usage
```

## What this playbook does NOT cover

- Private control-plane workflows that drive cluster ops from a
  laptop. Those are inherently private (per-user CLI credentials,
  personal notes) and belong in a double-wrapper workflow, not here.
