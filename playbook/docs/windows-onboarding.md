# Windows onboarding — PowerShell / OpenSSH gotchas

Windows 10 / 11 is a supported but fiddly platform for C3SE work.
This page catalogues the nine things that bite first-time users so
you can dodge them. All findings are confirmed on:

- Windows 11 Enterprise (10.0.26200)
- PowerShell 5.1 (`powershell.exe`) — the system default
- Built-in OpenSSH 9.5p2
- Git-bash via Git for Windows (optional)

If you can use macOS or Linux for the laptop side, you'll save
yourself an afternoon of the below. If you're on Windows, read once
before starting the SSH bootstrap and keep this doc open.

## 1. `bash` from PowerShell routes to WSL

**Symptom**: `bash _scripts/setup-ssh.sh` from PowerShell appears to
succeed but afterwards `Get-Content ~\.ssh\id_ed25519_c3se.pub` says
the file doesn't exist.

**Diagnosis**: Windows 10/11 ships `C:\Windows\System32\bash.exe`
that routes to WSL. When resolved first on PATH, everything runs
inside WSL's ext4 filesystem where `/home/<wsl-user>` is real but
invisible to Windows-side tools. The key ends up trapped in a VHD
nobody subsequently reads.

**Fix** (pick one):

- **Preferred**: run `.ps1` variants of any setup script. PowerShell's
  `~` always resolves to `$env:USERPROFILE` — unambiguous.
- **If you must run `.sh`**: launch from real Git-bash
  (`C:\Program Files\Git\usr\bin\bash.exe`), NOT from PowerShell's
  `bash` shim.
- **If writing a script yourself**: prefer `$USERPROFILE` over `$HOME`
  in bash scripts that may be launched from PowerShell:

  ```bash
  if [ -n "${USERPROFILE:-}" ]; then
      if command -v cygpath >/dev/null 2>&1; then
          HOME_DIR=$(cygpath -u "$USERPROFILE")
      else
          HOME_DIR=$(printf '%s' "$USERPROFILE" | sed -e 's|\\|/|g' -e 's|^\([A-Za-z]\):|/\L\1|')
      fi
  else
      HOME_DIR="$HOME"
  fi
  ```

## 2. PowerShell 5.x writes UTF-8 BOM

**Symptom**: every `ssh` command fails after running a setup script:

```
C:\Users\<cid>\.ssh\config line 1: no argument after keyword "\357\273\277"
C:\Users\<cid>\.ssh\config: terminating, 1 bad configuration options
```

`\357\273\277` = `EF BB BF` = the UTF-8 byte-order mark.

**Diagnosis**: `Add-Content -Encoding utf8` in Windows PowerShell 5.x
emits UTF-8 *with* BOM. OpenSSH's config parser rejects any file
starting with a BOM. PowerShell 7+ fixed this with `-Encoding utf8NoBOM`
but the Chalmers default is still 5.x.

**Fix**: write via .NET with a BOM-suppressing encoder:

```powershell
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::AppendAllText($cfg, $stanza + [Environment]::NewLine, $utf8NoBom)
```

**Remove a BOM from an existing config**:

```powershell
$raw = [System.IO.File]::ReadAllBytes("$HOME\.ssh\config")
if ($raw[0] -eq 0xEF -and $raw[1] -eq 0xBB -and $raw[2] -eq 0xBF) {
    [System.IO.File]::WriteAllBytes("$HOME\.ssh\config", $raw[3..($raw.Length - 1)])
    Write-Host "BOM stripped."
}
```

Quick check for a BOM:

```powershell
[System.IO.File]::ReadAllBytes("$HOME\.ssh\config") | Select-Object -First 3
```

A BOM-free file does NOT start with `239, 187, 191`.

## 3. Windows OpenSSH lacks `ssh-copy-id`

**Symptom**:

```
ssh-copy-id : The term 'ssh-copy-id' is not recognized as the name of a cmdlet...
```

**Diagnosis**: `ssh-copy-id` is a Unix shell script bundled with most
distros' OpenSSH, omitted from Microsoft's Win32 port.

**Fix** — the Windows-native equivalent, run from PowerShell:

```powershell
$pub = Get-Content "$HOME\.ssh\id_ed25519_c3se.pub" -Raw
$remote = "mkdir -p ~/.ssh && chmod 700 ~/.ssh && printf '%s' '$pub' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
ssh <cid>@alvis2.c3se.chalmers.se $remote
```

See the [`ssh-bootstrap.md` step 5](ssh-bootstrap.md#5-authorize-your-public-key-on-alvis)
for context.

## 4. PowerShell line-wrap breaks pasted commands

**Symptom**: you paste the `Get-Content ... | ssh ... "mkdir -p ..."`
one-liner from a web page and PowerShell's terminal wraps it visually.
The continuation prompt `>>` shows up between `chmod 600` and its
argument. The remote bash parses it as two separate commands, the
`chmod` is broken in half, and `authorized_keys` ends up with default
umask perms → `sshd` silently falls back to password. You spend an
hour debugging "my key isn't working".

**Diagnosis**: PowerShell's multi-line input mode triggers on
unclosed quotes at end of line. When pasting long commands with
embedded quotes, the terminal wraps visually but PS treats the newline
as literal input.

**Fix**: assign the remote command to a variable first. This avoids
any quote-nesting issues:

```powershell
$remote = "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
Get-Content "$HOME\.ssh\id_ed25519_c3se.pub" | ssh <cid>@alvis2.c3se.chalmers.se $remote
```

## 5. `authorized_keys` default umask rejected by StrictModes

**Symptom**: the key appears authorized but every `ssh alvis` falls
back to a password prompt. Manual login with `ssh <cid>@alvis2 ...`
also prompts for password.

**Diagnosis**: `cat >> ~/.ssh/authorized_keys` via an SSH pipe creates
the file with the remote shell's default umask (typically 0002 →
file perms `rw-rw-r--` = 664). OpenSSH's StrictModes rejects
group-writable `authorized_keys`.

**Fix**: always `chmod 600 ~/.ssh/authorized_keys` *after* the cat.
The ssh-bootstrap one-liner does this; but verify after the fact:

```bash
ssh <cid>@alvis2.c3se.chalmers.se "ls -l ~/.ssh/authorized_keys"
```

Must show `-rw-------`. If not:

```bash
ssh <cid>@alvis2.c3se.chalmers.se "chmod 600 ~/.ssh/authorized_keys && chmod 700 ~/.ssh"
```

## 6. `C3SE_quota` crashes over non-PTY SSH

**Symptom**:

```
Traceback (most recent call last):
  File "/usr/local/bin/C3SE_quota", line 65, in <module>
    curses.setupterm()
_curses.error: setupterm: could not find terminfo database
```

**Diagnosis**: `C3SE_quota` calls `curses.setupterm()` at import
time. When invoked over SSH without `-t` (no PTY), `$TERM` is empty
and curses can't initialise.

**Fix**: prefix with a TERM assignment:

```bash
ssh alvis "export TERM=xterm-256color; C3SE_quota"
```

Alternative: use `ssh -t alvis C3SE_quota` — forces PTY allocation.
Works for interactive one-shots, but conflicts with piped-stdin
patterns like `ssh alvis 'bash -s' < script.sh`.

**Applies to any C3SE CLI tool** that uses curses (`projinfo`,
some partition-specific helpers). When in doubt, prefix `TERM`.

## 7. SSH fingerprint verification (TOFU)

**Symptom**: not an error — a process gap. On first connect OpenSSH
shows:

```
The authenticity of host 'alvis2.c3se.chalmers.se (...)' can't be established.
ED25519 key fingerprint is SHA256:...
Are you sure you want to continue connecting (yes/no/[fingerprint])?
```

If you type `yes` without cross-checking, you're vulnerable to an
MITM.

**Fix**: verify the displayed fingerprint matches C3SE's published
list BEFORE typing `yes`. See
[`ssh-bootstrap.md` step 4](ssh-bootstrap.md#4-verify-the-expected-host-fingerprint-before-first-connect)
for the expected Alvis values and the C3SE docs URL.

## 8. `NativeCommandError` wrapping (cosmetic)

**Symptom**: `ssh -v alvis` prints a red PowerShell error block:

```
ssh : OpenSSH_for_Windows_9.5p2, LibreSSL 3.8.2
At line:1 char:1
    + CategoryInfo          : NotSpecified: (OpenSSH_for_Win...:String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError
```

**Diagnosis**: PowerShell 5.x wraps any stderr output from native
`.exe`s into a PowerShell error record. `ssh -v` writes its diagnostic
banner to stderr, so it gets flagged as an "error" even though ssh
exited 0.

**Fix**: append `2>&1` to merge streams:

```powershell
ssh -v alvis 2>&1
```

Or run via `cmd /c` to bypass PowerShell's native-command wrapping:

```powershell
cmd /c "ssh -v alvis"
```

Check the actual exit code with `$LASTEXITCODE` — `0` means success
regardless of red output.

## 9. Recommended onboarding path

Based on the eight pitfalls above, the lowest-friction Windows setup
for C3SE is:

1. **Use PowerShell, not bash-via-PowerShell, for anything touching
   `~\.ssh\`.**
2. **Run `.ps1` variants of setup scripts** when both exist.
3. **If you prefer a Unix shell**, launch real Git-bash from the
   Start menu, not PowerShell's `bash` shim.
4. **Verify `~/.ssh/config` has no BOM** (§2) after any automated
   write to it.
5. **Trust but verify**: `ssh alvis true && echo OK` is your
   smoke test; silent success = done.

If any of this breaks — drop back into
[`ssh-bootstrap.md` troubleshooting table](ssh-bootstrap.md#troubleshooting-quick-reference)
which maps symptoms back to specific sections above.

## See also

- [`ssh-bootstrap.md`](ssh-bootstrap.md) — end-to-end step-by-step
- [`transfer-methods.md`](transfer-methods.md) — `ssh` / `rsync` /
  `sshfs` daily recipes
- [`gotchas.md`](gotchas.md) — non-Windows-specific pitfalls
