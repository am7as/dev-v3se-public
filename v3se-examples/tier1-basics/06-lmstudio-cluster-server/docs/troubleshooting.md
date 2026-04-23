# Troubleshooting — `06-lmstudio-cluster-server`

Symptom → cause → fix for the failures that actually happen.

## 1. SIF build fails with `404 Not Found` on the LM Studio AppImage

**Symptom.** `apptainer build lmstudio.sif apptainer/lmstudio.def`
dies inside `%post` with:

```
curl: (22) The requested URL returned error: 404
FATAL: While performing build: ... post proc: exit status 22
```

**Cause.** LM Studio rotates its installer URLs on every release.
The `apptainer/lmstudio.def` recipe pins a specific
`installers.lmstudio.ai/linux/x64/<ver>/LM-Studio-<ver>-linux-x64.AppImage`
and the pinned version has been removed upstream.

**Fix.** Check the current version at <https://lmstudio.ai/docs/cli>
and update the URL in `apptainer/lmstudio.def`:

```diff
-curl -fsSL https://installers.lmstudio.ai/linux/x64/0.3.5/LM-Studio-0.3.5-linux-x64.AppImage \
+curl -fsSL https://installers.lmstudio.ai/linux/x64/0.3.12/LM-Studio-0.3.12-linux-x64.AppImage \
     -o /opt/lmstudio/lms.AppImage
```

Rebuild. If a GUI runtime lib is now also missing, expand the
`apt-get install` list in the same block.

## 2. `ssh -L …` prints `channel 3: open failed: connect failed: Connection refused`

**Symptom.** The tunnel opens, but the first curl / `pixi run infer`
call errors with `Connection refused`.

**Cause.** One of:

- The sbatch is still in `PD` (pending) — no server on the node yet.
- The job is `R` but `results/lmstudio-port.txt` is stale from a
  previous run, so you forwarded the wrong port.
- LM Studio is still initializing (it takes 10–30 s after `server
  start` before `/v1` returns 200).
- The sbatch crashed between `host:port` being written and the server
  binding.

**Fix.**

```bash
ssh alvis squeue -u $USER -o "%i %T %R"   # verify R
ssh alvis cat /cephyr/users/<cid>/Alvis/<wrapper>/results/lmstudio-port.txt
ssh alvis tail -n 50 /cephyr/users/<cid>/Alvis/<wrapper>/slurm-lmstudio-server-*.out
```

If the port looks wrong, the safest reset: cancel + resubmit, re-read
the two files *after* the job reaches `R`, re-open the tunnel.

## 3. Cephyr quota exploded right after first model pull

**Symptom.** `C3SE_quota` on the next login shows you over the 30 GiB
or 60 000-file limit; `du --inodes -d 2 ~` points at `~/.cache/lm-studio/`.

**Cause.** `LMSTUDIO_CACHE_DIR` was empty in `.env`, so LM Studio fell
back to its in-container default, which ultimately resolved to
`$HOME/.cache/lm-studio/` — on Cephyr. A single 8 B GGUF plus index /
manifest files is a couple thousand files and 5+ GiB.

**Fix.**

1. Cancel the job (`scancel <jobid>`).
2. Move or delete the rogue cache:
   ```bash
   rm -rf ~/.cache/lm-studio
   ```
3. Set `LMSTUDIO_CACHE_DIR` in `.env`:
   ```ini
   LMSTUDIO_CACHE_DIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/lmstudio
   ```
4. Verify the sbatch picks it up — look for the `--bind
   $LMSTUDIO_CACHE:/tmp/lmstudio` line in the log.
5. Resubmit.

## 4. Job stuck in `PD` for hours

**Symptom.** `squeue -u $USER` shows `PENDING` and the reason column
is not `Resources` / `Priority`.

**Cause.** Most common: the allocation is exhausted (`AssocGrpCpuLimit`,
`QOSMaxWallDurationPerJobLimit`), or you asked for a GPU tier your
project doesn't have.

**Fix.**

```bash
squeue -u $USER -o "%i %T %R"
```

- `AssocGrpCpuLimit` — contact your PI or wait for the monthly reset.
- `QOSMaxJobsPerUserLimit` — cancel an old job.
- `PartitionConfig` / `ReqNodeNotAvail` — the requested GPU type isn't
  available in your partition; lower `--gpus-per-node=T4:1`.
- Infinite `Priority` wait on A100 — A100 queues are long; consider
  `A40:1` if the model fits.

## 5. `lms: command not found` inside the job log

**Symptom.** The sbatch log has `bash: lms: command not found` or
`apptainer: FATAL: While starting runscript: command not found`.

**Cause.** The SIF was built but the AppImage extract failed silently.
`/usr/local/bin/lms` is a symlink into `/opt/lmstudio/lmstudio/AppRun`
— if the extract didn't produce that tree, the symlink dangles.

**Fix.** Rebuild, watching for AppImage errors:

```bash
apptainer build --force lmstudio.sif apptainer/lmstudio.def 2>&1 | tee build.log
grep -Ei "error|fail" build.log
```

If the AppImage extract aborts with a missing shared lib, add it to
the `apt-get install` list in the `.def` and rebuild.

## 6. Client sees `Connection refused` on laptop after the tunnel was working

**Symptom.** The first few `pixi run infer` calls worked; now every call
fails with `Connection refused` even though the sbatch is still `R`.

**Cause.** Either the SSH `ControlMaster` session died (laptop slept,
Wi-Fi flapped, jump host timed out), or the server job crashed after
the port file was written.

**Fix.**

1. Check the server is still alive:
   ```bash
   ssh alvis squeue -u $USER
   ```
2. If the job is still `R`, reset the tunnel:
   ```bash
   ssh -O exit alvis        # kill the stale ControlMaster
   ssh -L $PORT:$HOST:$PORT alvis
   ```
3. If the job is gone, inspect `slurm-lmstudio-server-*.err` for the
   crash, bump `--time` or `--mem` as needed, resubmit.

## 7. Docker on Linux laptop can't resolve `host.docker.internal`

**Symptom.** Local-only variant works on macOS / Windows but on Linux,
`pixi run infer` inside the container errors with
`Name or service not known: host.docker.internal`.

**Cause.** Docker for Linux historically does not resolve
`host.docker.internal` — it's a Docker Desktop convenience.

**Fix.** Add a host alias in `docker-compose.yml`:

```yaml
services:
  dev:
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

Then `docker compose down && docker compose up -d dev`. Or skip the
Docker indirection entirely: run `pixi install` + `pixi run infer`
on the Linux host with `OPENAI_BASE_URL=http://localhost:1234/v1`.

## 8. Model download hangs on first completion request

**Symptom.** The tunnel is up, the first `pixi run infer` sits for 10+
minutes, the server log shows `resolving <org>/<model>…` and no
progress bar.

**Cause.** LM Studio pulls GGUF weights lazily on first completion
request. For a 40+ GiB model on a slow compute-node egress, that's
legitimately 20–30 min. Sometimes the HF CDN flakes and the connection
stalls.

**Fix.**

- Be patient once — subsequent runs reuse the Mimer cache and start in
  seconds.
- If stalled > 20 min, `scancel` and pre-pull on the login node (see
  section 6 of [modification.md](modification.md)), then resubmit.
