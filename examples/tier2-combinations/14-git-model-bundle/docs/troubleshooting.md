# Troubleshooting — `14-git-model-bundle`

Common failures and how to fix them. The first half is about the
**build** (SIF or Docker image); the second half is about **runtime**.

## 1. Clone fails during the build

**Symptom.** `apptainer build bundle.sif ...` aborts in `%post` with:

```
fatal: could not read Username for 'https://...': No such device or address
# or
fatal: repository 'https://example.invalid/...' not found
```

**Cause.** Either `MODEL_REPO` is still the placeholder
(`https://example.invalid/...`), the URL is wrong, or the build host
can't authenticate.

**Fix.** Test the clone outside the build first — it's much faster
than a failed SIF build:

```bash
set -a; . ./.env; set +a
git ls-remote "$MODEL_REPO"
```

If that fails, the SIF build will too. Common root causes:

- Typo in `MODEL_REPO`.
- Private repo, no SSH key on the build host (see `setup.md` §4).
- HTTPS PAT expired.

Once `git ls-remote` succeeds, re-run `bash scripts/build-sif.sh`.

## 2. `git lfs pull` hangs or times out during build

**Symptom.** `%post` reaches `git lfs pull` and sits for tens of
minutes, eventually timing out. Often happens with repos storing 10+
GiB of weights in LFS.

**Cause.** LFS is not designed to download efficiently inside an
Apptainer build sandbox — the `overlayfs` scratch space pays a heavy
IO penalty, and there's no resumption between build attempts.

**Fix — pre-download weights, skip LFS in %post:**

1. On a host with plenty of disk:

   ```bash
   git clone "$MODEL_REPO" /tmp/model-src
   cd /tmp/model-src
   git lfs pull
   tar -czf /mimer/NOBACKUP/groups/<naiss-id>/<cid>/model-src.tar.gz .
   ```

2. Edit `apptainer/bundle.def` to **copy** the tarball via `%files`
   instead of cloning:

   ```diff
   +%files
   +    /mimer/NOBACKUP/groups/<naiss-id>/<cid>/model-src.tar.gz /tmp/model-src.tar.gz

    %post
        set -e
   -    mkdir -p /opt/model
   -    cd /opt/model
   -    git clone --depth 1 --branch "${MODEL_REF}" "${MODEL_REPO}" .
   -    git lfs pull || true
   +    mkdir -p /opt/model
   +    tar -xzf /tmp/model-src.tar.gz -C /opt/model
   +    rm -f /tmp/model-src.tar.gz
   ```

3. Rebuild. The build is now IO-bound on tarball extraction, not
   network + LFS.

## 3. SIF runs but can't find the weights

**Symptom.**

```
apptainer run --nv bundle.sif pixi run infer --prompt "hi"
# → FileNotFoundError: /opt/model/model.safetensors
```

or `OSError: /opt/model does not contain any model files`.

**Cause.** The repo uses git-lfs but the build's `git lfs pull` was
silently skipped (it's wrapped in `|| true` in the default
`bundle.def`). Post-build `rm -rf .git` then erased the evidence.

**Fix.** Verify the repo actually uses LFS:

```bash
git clone --no-checkout "$MODEL_REPO" /tmp/check
cd /tmp/check
git lfs ls-files | head
```

If `git lfs ls-files` lists weights, the build needs LFS. Confirm
`git-lfs` is installed in `%post` (the default def does this) and
remove the `|| true` so the build fails loudly on LFS errors:

```diff
-    git lfs pull || true
+    git lfs pull
```

Rebuild. If weights are stored some other way (e.g. downloaded by
the repo's own `setup.py`), follow `modification.md` §5 to
customise the install step.

## 4. `MODEL_DIR not found` at run time

**Symptom.** The job log says:

```
OSError: /opt/model not found
```

even though `bundle.sif` definitely contains it.

**Cause.** The sbatch or `apptainer run` invocation uses `dev.sif`,
not `bundle.sif`. `dev.sif` doesn't bake in weights — it's the
lightweight image for host-bind dev work.

**Fix.** Check the sbatch. The default line is:

```bash
SIF="${SIF:-./dev.sif}"
```

Override at submit time:

```bash
sbatch --export=ALL,SIF=./bundle.sif,PROMPT="..." slurm/gpu-t4.sbatch
```

Or edit `slurm/gpu-t4.sbatch` to change the default:

```diff
-SIF="${SIF:-./dev.sif}"
+SIF="${SIF:-./bundle.sif}"
```

## 5. Cephyr fills with apptainer build cache

**Symptom.** Running `bash scripts/build-sif.sh` on Alvis, after
~10 minutes you hit:

```
FATAL: While performing build: ... no space left on device
```

and `C3SE_quota` shows Cephyr file count spiked.

**Cause.** `APPTAINER_CACHEDIR` defaults to
`~/.apptainer/cache/` — on Alvis, that's on Cephyr. Apptainer dumps
multi-GiB layer blobs during a build.

**Fix.** Always redirect to Mimer before a big build:

```bash
export APPTAINER_CACHEDIR=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/apptainer-cache
mkdir -p "$APPTAINER_CACHEDIR"
bash scripts/build-sif.sh
```

Clean up any leaked Cephyr cache:

```bash
rm -rf ~/.apptainer/cache/
```

Consider adding the `APPTAINER_CACHEDIR` export to `~/.bashrc` on
Alvis so you never forget.

## 6. 401 on `MODEL_REPO` clone

**Symptom.**

```
remote: Repository not found.
fatal: Authentication failed for 'https://github.com/<org>/<private>'
```

**Cause.** Private repo, no creds on the build host.

**Fix — SSH (preferred):**

1. `ssh-keygen -t ed25519 -f ~/.ssh/id_model_repo`.
2. Paste `~/.ssh/id_model_repo.pub` into GitHub/GitLab deploy keys
   (read-only).
3. `.env`: `MODEL_REPO=git@github.com:<org>/<repo>.git`.
4. On Alvis, either copy the private key to `~/.ssh/` on Alvis **or**
   use `ForwardAgent yes` in `~/.ssh/config` and run
   `ssh-add ~/.ssh/id_model_repo` on laptop before `ssh alvis`.
5. Test: `git ls-remote $MODEL_REPO`.

**Fix — HTTPS PAT (one-off):**

```ini
MODEL_REPO=https://<user>:<pat>@github.com/<org>/<repo>.git
```

Rotate the PAT soon — it is visible in the build log and shell history.

## 7. Gated HF weights fail to download during build

**Symptom.** The model repo's `setup.py` or `requirements.txt` tries
to fetch weights from HuggingFace and fails:

```
huggingface_hub.utils._errors.RepositoryNotFoundError: 401 Client Error.
```

**Cause.** The build environment has no `HF_TOKEN` and the weights
are gated.

**Fix.** See `modification.md` §4. Short version: add `HF_TOKEN` to
`.env`, forward it as a build arg in `build-sif.sh`, export it in
`%post`. Confirm the HF account already accepted the licence in a
browser — token alone isn't enough.

## 8. Runs on CPU despite GPU allocation

**Symptom.** `gpu-t4` job shows `device: cpu` in the result JSON.

**Cause.** Missing `--nv` flag in the sbatch's `apptainer run` line.

**Fix.** The default sbatch includes it (`apptainer run --nv ...`).
Check any custom sbatches you wrote. Verify from inside the container:

```bash
apptainer run --nv bundle.sif python3 -c "import torch; print(torch.cuda.is_available())"
```

`True` = OK. `False` + `--nv` already set = something is off with the
CUDA-driver-in-container setup; typically a mismatch between the SIF's
CUDA version (`12.1` by default) and the host driver. Rebuild with a
matching base image.
