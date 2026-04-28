# Troubleshooting — `07-ollama-cluster-server`

Symptom → cause → fix for the failures that actually happen.

## 1. SIF build fails on `ollama/install.sh`

**Symptom.** `apptainer build ollama.sif apptainer/ollama.def` dies
inside `%post` with:

```
curl: ... 404
FATAL: While performing build: ... post proc: exit status 22
```

Or (more common): the script runs but then fails to launch because
the installer tried to enable a systemd unit that doesn't exist
inside an Apptainer build.

**Cause.** `ollama.com/install.sh` is a living script; upstream
occasionally changes URL paths, adds `systemctl` calls, or bumps
required glibc. A build that worked three months ago can stop.

**Fix.**

1. Look at upstream current form:
   ```bash
   curl -fsSL https://ollama.com/install.sh | less
   ```
2. If the installer is still sane but now invokes `systemctl`, pin a
   release tarball directly in `apptainer/ollama.def` instead:
   ```
   %post
       curl -fsSL https://github.com/ollama/ollama/releases/download/v0.4.7/ollama-linux-amd64.tgz \
           | tar -xz -C /usr/local
   ```
3. Rebuild: `apptainer build --force ollama.sif apptainer/ollama.def`.

## 2. Tunnel refuses connection

**Symptom.** SSH tunnel opens, but `pixi run infer` on the laptop
errors with `Connection refused`.

**Cause.** One of:

- The sbatch is still `PD` — no server on the node yet.
- The sbatch is `R` but the `ollama pull` step hasn't finished, so
  `ollama serve` is up but on a different port or still initializing.
- You're forwarding a stale `ollama-port.txt` from a previous run.
- The job crashed between writing the port file and binding.

**Fix.**

```bash
ssh alvis squeue -u $USER -o "%i %T %R"   # verify R
ssh alvis cat /cephyr/users/<cid>/Alvis/<wrapper>/results/ollama-port.txt
ssh alvis tail -n 100 /cephyr/users/<cid>/Alvis/<wrapper>/slurm-ollama-server-*.out
```

Look for the line `Ollama ready on port <port> with model <model>` in
the job log — that's the sign the pull finished and the server is
actually accepting requests. If missing, wait a couple of minutes
(large models take time).

## 3. Cephyr quota exploded after first `ollama pull`

**Symptom.** `C3SE_quota` shows you near or over the 30 GiB / 60 000-file
limit immediately after the first job; `du --inodes -d 2 ~` points at
`~/.ollama/models/`.

**Cause.** `OLLAMA_MODELS` was empty in `.env`, so Ollama fell back
to `$HOME/.ollama/models` — on Cephyr. A single `llama3.1:8b` pull is
~5 GiB split across hundreds of blob files; `llama3.1:70b` is 40+ GiB.

**Fix.**

1. Cancel the job (`scancel <jobid>`).
2. Delete the rogue cache:
   ```bash
   rm -rf ~/.ollama
   ```
3. Set `OLLAMA_MODELS` in `.env`:
   ```ini
   OLLAMA_MODELS=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/ollama/models
   ```
4. Verify the sbatch picks it up — look for the
   `--bind $OLLAMA_CACHE:/tmp/ollama-models` line in the log.
5. Resubmit.

## 4. Job stuck in `PENDING` forever

**Symptom.** `squeue -u $USER` shows `PENDING` and the reason column
is not `Resources` / `Priority`.

**Cause.** Allocation exhausted, too many jobs, or a GPU tier your
project doesn't have.

**Fix.**

```bash
squeue -u $USER -o "%i %T %R"
```

- `AssocGrpCpuLimit` / `AssocMaxCpuPerAccount` — contact your PI.
- `QOSMaxJobsPerUserLimit` — cancel an old job.
- `PartitionConfig` / `ReqNodeNotAvail` — the requested GPU type isn't
  available; lower to `T4:1`.
- Infinite `Priority` on A100 — A100 queues are long; consider `A40:1`
  if the model fits.

## 5. `ollama pull` hangs during first run

**Symptom.** Job log shows `pulling <digest>…` and then no progress
for 10+ minutes.

**Cause.** Ollama's CDN flakes periodically; the compute-node egress
is slow compared to the login node; very large models (30 B+) can
legitimately take 20–30 min.

**Fix.**

- First: wait. A 40 GiB download on a slow link is a real 20+ min.
- If stuck beyond ~30 min, cancel and retry — transient CDN errors
  usually clear within the hour:
  ```bash
  scancel <jobid>
  sbatch slurm/ollama-server.sbatch
  ```
- Better: pre-pull on the login node once per new model (see section
  6 of [modification.md](modification.md)). Subsequent job starts are
  instant.

## 6. Client sees `Connection refused` on laptop after tunnel was working

**Symptom.** First `pixi run infer` worked; now every call fails with
`Connection refused`, even though the job is still `R`.

**Cause.** Either the SSH `ControlMaster` session died (laptop slept,
Wi-Fi blinked), or the server job died after the port file was
written.

**Fix.**

1. Check the job:
   ```bash
   ssh alvis squeue -u $USER
   ```
2. If the job is still `R`, reset the tunnel:
   ```bash
   ssh -O exit alvis
   ssh -L $PORT:$HOST:$PORT alvis
   ```
3. If the job died, inspect `slurm-ollama-server-*.err`, bump
   `--time` or `--mem` as needed, resubmit.

## 7. Port `11434` already in use on the laptop

**Symptom.** `ssh -L 11434:...` fails with `bind [::1]:11434: Address
already in use`.

**Cause.** A local `ollama serve` (installed as a service by the
Ollama installer on macOS / Windows / systemd Linux) is already
listening on 11434.

**Fix.** Either stop the local service, or forward to a different
laptop port:

```bash
# macOS
brew services stop ollama

# Linux systemd
sudo systemctl stop ollama

# Windows: Settings → Apps → Ollama → Quit, or:
taskkill /IM ollama.exe /F

# OR, forward to a different laptop-side port:
ssh -L 9999:$HOST:$PORT alvis
OPENAI_BASE_URL=http://localhost:9999/v1 pixi run infer --prompt "hi" --model $OLLAMA_MODEL
```

## 8. Docker on Linux laptop can't reach `host.docker.internal`

**Symptom.** Local-only variant works on macOS / Windows but on Linux,
`pixi run infer` inside the container errors with
`Name or service not known: host.docker.internal`.

**Cause.** Docker for Linux does not resolve `host.docker.internal`
out of the box — it's a Docker Desktop convenience.

**Fix.** Add a host alias in `docker-compose.yml`:

```yaml
services:
  dev:
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

Then `docker compose down && docker compose up -d dev`. Or skip the
Docker indirection entirely: run `pixi install` + `pixi run infer`
on the Linux host with `OPENAI_BASE_URL=http://localhost:11434/v1`.
