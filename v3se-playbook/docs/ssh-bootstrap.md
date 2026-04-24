# SSH bootstrap — C3SE clusters (Alvis + Vera)

End-to-end walkthrough: "I have a CID" → "`ssh alvis` works silently".

Dual-platform (Linux / macOS / Windows). Windows-specific quirks are
cross-linked to [`windows-onboarding.md`](windows-onboarding.md) — if
you're on Windows, keep both docs open side by side.

## Prerequisites

- A Chalmers CID with Alvis (and optionally Vera) access.
- Chalmers VPN client if you're off-campus. `alvis2` and `vera2` are
  not reachable from the public internet without it.
- An SSH client:
  - **Linux / macOS**: built-in OpenSSH.
  - **Windows 10 / 11**: built-in OpenSSH. Verify with
    `Get-Command ssh` — should resolve to
    `C:\Windows\System32\OpenSSH\ssh.exe`. If missing, install via
    *Settings → Apps → Optional features → OpenSSH Client*.

## 1. Check network connectivity

**PowerShell:**

```powershell
Test-NetConnection -ComputerName alvis2.c3se.chalmers.se -Port 22
```

Look for `TcpTestSucceeded : True`.

**bash / zsh:**

```bash
nc -z -v alvis2.c3se.chalmers.se 22
```

If this times out, you're off-network — connect to Chalmers VPN and
re-run step 1.

## 2. Generate an SSH key pair

Use a project-specific key name so it can be revoked independently of
any other keys you have.

**PowerShell:**

```powershell
ssh-keygen -t ed25519 -f "$HOME\.ssh\id_ed25519_c3se" -C "<cid>@c3se"
```

**bash / zsh:**

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_c3se -C "<cid>@c3se"
```

Press Enter twice for no passphrase (convenient, least secure), or set
one (use `ssh-agent` to unlock once per session).

> **Windows users**: run this from **PowerShell**, not from `bash`.
> PowerShell's `bash` often routes to WSL and the key ends up in WSL's
> ext4 VHD, invisible to Windows OpenSSH. See
> [`windows-onboarding.md` §1](windows-onboarding.md#1-bash-from-powershell-routes-to-wsl).

## 3. Write your `~/.ssh/config`

Add these two stanzas (create the file if it doesn't exist):

```
Host alvis
  HostName alvis2.c3se.chalmers.se
  User <cid>
  IdentityFile ~/.ssh/id_ed25519_c3se
  ControlMaster auto
  ControlPath ~/.ssh/control-%r@%h:%p
  ControlPersist yes
  ServerAliveInterval 60
  ServerAliveCountMax 10

Host cephyr-transfer
  HostName vera2.c3se.chalmers.se
  User <cid>
  IdentityFile ~/.ssh/id_ed25519_c3se
  ControlMaster auto
  ControlPath ~/.ssh/control-%r@%h:%p
  ControlPersist yes
```

Replace `<cid>` with your actual Chalmers CID.

`ControlMaster auto` + `ControlPersist yes` reuses a single TCP
connection across multiple `ssh` / `rsync` / `scp` commands —
dramatically faster for scripted loops.

> **Windows users**: do NOT append to `~/.ssh/config` with
> `Add-Content -Encoding utf8` on PowerShell 5.x — it writes a BOM
> that OpenSSH refuses. See
> [`windows-onboarding.md` §2](windows-onboarding.md#2-powershell-5x-writes-utf-8-bom).

## 4. Verify the expected host fingerprint (before first connect)

**This is the one step that most guides skip, and it's the step that
actually keeps you safe from MITM.**

Cross-check the fingerprint that OpenSSH will show you against C3SE's
official list:

<https://www.c3se.chalmers.se/documentation/connecting/ssh/>

At the time of writing, the expected Alvis fingerprints are:

| Algorithm | Fingerprint                                                    |
|-----------|----------------------------------------------------------------|
| ED25519   | `SHA256:GXaNJmWD2Jp9wFj03aH2zxsBIW9dhtiGjgJ2bHCzWhI`            |
| ECDSA     | `SHA256:xt8pNqCyCOaveKEXhKkq5KJ7k8H+TManiiF4ry3EmFE`            |
| RSA       | `SHA256:IywVhz/C4f/4Uq11b3Fwp5ptEhVDkV/e+xq/aRdtQag`            |

(Verify with the URL above before trusting — C3SE may rotate keys.)

The Vera fingerprints are published on the same page.

**Never type `yes` at the TOFU prompt without first confirming the
shown fingerprint matches one of the three above.**

## 5. Authorize your public key on Alvis

### Linux / macOS — use `ssh-copy-id`

```bash
ssh-copy-id -i ~/.ssh/id_ed25519_c3se.pub <cid>@alvis2.c3se.chalmers.se
```

Enter your Chalmers password (this is the last time you need it for key-auth).

### Windows — `ssh-copy-id` does NOT exist in Windows OpenSSH

Use this PowerShell one-liner instead:

```powershell
$pub = Get-Content "$HOME\.ssh\id_ed25519_c3se.pub" -Raw
$remote = "mkdir -p ~/.ssh && chmod 700 ~/.ssh && printf '%s' '$pub' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
ssh <cid>@alvis2.c3se.chalmers.se $remote
```

Note: **assign the remote command to a variable first** (as shown), do
NOT paste a long quoted command directly into PowerShell — it may wrap
visually and break between the `chmod` and its argument. See
[`windows-onboarding.md` §4](windows-onboarding.md#4-powershell-line-wrap-breaks-pasted-commands).

Enter your Chalmers password when prompted.

## 6. Verify permissions on the cluster side

`sshd` quietly rejects `authorized_keys` files with wrong permissions
(StrictModes). Check now so you don't waste time debugging silent
fallback-to-password later.

```bash
ssh <cid>@alvis2.c3se.chalmers.se "ls -ld ~/.ssh && ls -l ~/.ssh/authorized_keys"
```

Expected output:

```
drwx------  2 <cid> <group>  ...  /home/<cid>/.ssh
-rw-------  1 <cid> <group>  ...  /home/<cid>/.ssh/authorized_keys
```

If `~/.ssh/` is not `700` or `authorized_keys` is not `600`, re-run:

```bash
ssh <cid>@alvis2.c3se.chalmers.se "chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys"
```

## 7. First real connect (TOFU)

```bash
ssh alvis
```

OpenSSH prompts:

```
The authenticity of host 'alvis2.c3se.chalmers.se (...)' can't be established.
ED25519 key fingerprint is SHA256:GXaNJmWD2Jp9wFj03aH2zxsBIW9dhtiGjgJ2bHCzWhI.
Are you sure you want to continue connecting (yes/no/[fingerprint])?
```

**Cross-check** the shown fingerprint against step 4. If it matches,
type `yes`. You should land on the Alvis login node shell. Type
`exit` to return.

## 8. Silent-auth smoke test

```bash
ssh alvis true && echo "OK: key-auth works"
```

A silent `OK: key-auth works` means the bootstrap is done — no
password prompt, no TOFU prompt (already cached), nothing.

If you see a password prompt, check:

- `~/.ssh/config` has `IdentityFile ~/.ssh/id_ed25519_c3se`.
- The key was actually authorized (step 6 showed `-rw-------`).
- The remote `authorized_keys` contains your pub key:
  `ssh alvis "cat ~/.ssh/authorized_keys"`.

## 9. Quota check — the first C3SE tool

```bash
ssh alvis "export TERM=xterm-256color; C3SE_quota"
```

The `export TERM=xterm-256color` prefix is required because
`C3SE_quota` calls `curses.setupterm()` at startup, which fails over
non-PTY SSH. See
[`windows-onboarding.md` §6](windows-onboarding.md#6-c3se_quota-crashes-over-non-pty-ssh).

Expected output: a table of your Cephyr and Mimer usage. See
[`storage-model.md`](storage-model.md) for what the numbers mean.

## 10. Vera for transfers (optional — do this if you use rsync)

`vera2.c3se.chalmers.se` is the dedicated transfer host. Repeat steps
5 and 6 against Vera so `rsync -avh alvis:<path> ./` and the
`cephyr-transfer` alias work without password prompts.

```bash
ssh-copy-id -i ~/.ssh/id_ed25519_c3se.pub <cid>@vera2.c3se.chalmers.se
```

Then:

```bash
ssh cephyr-transfer true && echo "OK: vera key-auth works"
```

## Troubleshooting quick reference

| Symptom                                                | Likely cause                                              | Fix                                                                 |
|--------------------------------------------------------|-----------------------------------------------------------|---------------------------------------------------------------------|
| Timeout on `Test-NetConnection` / `nc -z`              | Off-campus without VPN                                    | Connect Chalmers VPN, re-run step 1                                 |
| "Permission denied (publickey)"                        | Key not authorized or `IdentityFile` missing from config  | Re-run steps 5-6; double-check step 3                               |
| Silent fall-back to password                           | `authorized_keys` perms wrong (StrictModes)               | `ssh <host> "chmod 600 ~/.ssh/authorized_keys"`                     |
| `no argument after keyword "\357\273\277"` at line 1   | `~/.ssh/config` has a UTF-8 BOM                            | See [`windows-onboarding.md` §2](windows-onboarding.md#2-powershell-5x-writes-utf-8-bom) |
| `_curses.error` from `C3SE_quota`                      | No PTY allocated over SSH                                 | Prefix with `export TERM=xterm-256color` (step 9)                   |
| `ssh-copy-id: not recognized` on Windows               | Not shipped in Microsoft's OpenSSH port                   | Use the PowerShell one-liner in step 5                              |
| Red `NativeCommandError` block from `ssh -v`           | PowerShell wraps native stderr as error                   | Append `2>&1` — the exit code is fine. See [`windows-onboarding.md` §8](windows-onboarding.md#8-nativecommanderror-wrapping-cosmetic) |
| Key ended up in WSL / you can't find the `.pub` file   | Ran `ssh-keygen` from `bash` inside PowerShell; it routed to WSL | Delete the WSL key, re-run step 2 from real PowerShell. See [`windows-onboarding.md` §1](windows-onboarding.md#1-bash-from-powershell-routes-to-wsl) |

## See also

- [`windows-onboarding.md`](windows-onboarding.md) — Windows / PS 5.x gotchas in detail
- [`transfer-methods.md`](transfer-methods.md) — daily `ssh` / `rsync` / `sshfs` recipes
- [`storage-model.md`](storage-model.md) — what Cephyr vs Mimer means
- [`push-to-cluster.md`](push-to-cluster.md) — moving code + data once SSH works
