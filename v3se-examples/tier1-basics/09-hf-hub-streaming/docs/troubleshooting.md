# Troubleshooting — `09-hf-hub-streaming`

Common failures and how to fix them. Ordered roughly by how often
each one bites. If your symptom is subtle (first run fast, every
later run slow), scan the headings — the "slow every job" section
probably applies.

## 1. Cephyr quota exploded on first run

**Symptom.** `C3SE_quota` shows Cephyr file count went from
~1 000 to ~60 000 after a single `gpu-t4` job. Further sbatches
queue forever because Slurm can't write job logs.

**Cause.** `HF_HOME` was never overridden. transformers fell back to
`~/.cache/huggingface/hub/` — and `$HOME` on Alvis is a Cephyr
symlink.

**Fix.**

```bash
# on Alvis
set -a; . ./.env; set +a
echo "$HF_HOME"        # MUST be under /mimer/, NOT ~ or /cephyr
```

If it's wrong, edit `.env`:

```ini
HF_HOME=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/<project>/.hf-cache
TRANSFORMERS_CACHE=/mimer/NOBACKUP/groups/<naiss-id>/<cid>/<project>/.hf-cache
```

Then clean up what leaked:

```bash
du -sh ~/.cache/huggingface/ 2>/dev/null
rm -rf ~/.cache/huggingface/
```

Re-run `C3SE_quota` — file count should drop back.

## 2. `Repository Not Found` or `401 Unauthorized`

**Symptom.** Job log contains:

```
huggingface_hub.utils._errors.RepositoryNotFoundError: 401 Client Error.
```

**Cause.** The model is gated (Llama family, `gemma-*-it`, Mistral
Instruct) and you haven't accepted the licence *or* `HF_TOKEN` is
missing / wrong.

**Fix.**

1. In a browser, visit `https://huggingface.co/<org>/<model>` and
   accept the licence with the same HF account that owns the token.
2. In `.env`: `HF_TOKEN=hf_xxxxxxxx`.
3. Verify from laptop before re-submitting:

   ```bash
   curl -sH "Authorization: Bearer $HF_TOKEN" \
     https://huggingface.co/api/models/$HF_MODEL | head -c 200
   ```

   A JSON blob with `"modelId"` = OK.
4. Copy `.env` to cluster (`scp` or re-export inside the sbatch).

## 3. Very slow on every job, even after the "first" download

**Symptom.** Job N downloads weights again even though job N-1 finished
successfully.

**Cause.** Every job landed on a different compute node **and** each
node has its own scratch-space `HF_HOME` (e.g. `/tmp/`, or the
sbatch's fallback `$PWD/.hf-cache` which turned into a fresh empty
dir because `$PWD` was different).

**Fix.** Point `HF_HOME` at a **Mimer path visible to every node**
(`/mimer/NOBACKUP/groups/...`). The first job downloads, all
subsequent jobs across all nodes read the cache.

```bash
grep -E '^(HF_HOME|TRANSFORMERS_CACHE)=' .env
# Both must be the same /mimer/... path.
```

## 4. `HF_HOME is under Cephyr/home` warning in the smoke log

**Symptom.** The job runs, but the log begins with:

```
UserWarning: HF_HOME=/cephyr/users/<cid>/... is under Cephyr/home.
On Alvis this will hit the 60k-file quota quickly. Prefer /mimer/... or /tmp/...
```

**Cause.** `src/hf_hub_streaming/model.py::_check_hf_home()` found a
dangerous path. The warning fires **before** the download starts,
giving you a chance to cancel.

**Fix.** Cancel the job (`scancel <jobid>`), correct `.env`, and
confirm the sbatch doesn't re-export `HF_HOME` to the wrong value.
The bundled sbatch is correct — check any custom sbatches you wrote.

## 5. Outbound HTTPS blocked on compute node

**Symptom.** Rare on Alvis, but possible with stricter firewalls or
offline partitions:

```
ConnectionError: Could not reach https://huggingface.co
```

**Cause.** Compute node has no outbound internet. The streaming
pattern cannot work under this constraint.

**Fix.** Pivot to a non-streaming example:

- `../08-hf-sif-bundle/` — bake weights into a SIF on a login node
  (which **does** have network), run offline.
- `../03-hf-shared-hub/` — if C3SE has already mirrored your model.

Before giving up, verify from a compute node:

```bash
srun --account=<naiss-id> --gpus-per-node=T4:1 --time=0-00:05:00 --pty bash
curl -sI https://huggingface.co/ | head -1
```

A `HTTP/2 200` means streaming works — the issue is something else
(token? proxy var?). Anything else confirms the firewall hypothesis.

## 6. Disk full mid-download

**Symptom.** Download starts, progresses to ~70 %, then:

```
OSError: [Errno 28] No space left on device
```

**Cause.** Mimer group quota or per-user cache dir full.

**Fix.**

```bash
ssh alvis
du -sh /mimer/NOBACKUP/groups/<naiss-id>/<cid>/<project>/.hf-cache
C3SE_quota                  # check Mimer row
```

Delete stale snapshots:

```bash
rm -rf /mimer/NOBACKUP/groups/<naiss-id>/<cid>/<project>/.hf-cache/models--<other-org>--<old-model>
```

Or request a larger Mimer quota via SUPR.

## 7. Model loads but generates gibberish

**Symptom.** `pixi run infer` returns — but `text` is empty, repeats
the prompt, or is garbled.

**Cause (common).** Wrong `AutoModelFor*` class for the architecture.
Base `gemma-2-2b` needs `AutoModelForCausalLM`; a LLaVA vision model
needs `AutoModelForImageTextToText`; an encoder-decoder like T5 needs
`AutoModelForSeq2SeqLM`.

**Cause (less common).** Dtype mismatch — `HF_DTYPE=float16` on a
model trained in bfloat16 can overflow.

**Fix.** Edit `src/hf_hub_streaming/model.py::load()` to import and
use the class the model card recommends. Reset `HF_DTYPE=auto` and
let transformers pick.

## 8. Laptop GPU not detected in the dev container

**Symptom.** `docker compose exec dev pixi run smoke` prints
`cuda_available: false` on a Windows laptop with an NVIDIA GPU.

**Cause.** The `deploy.resources.reservations.devices` block in
`docker-compose.yml` is commented out, or the NVIDIA Container
Toolkit isn't installed on the Docker host.

**Fix.** Uncomment the GPU stanza in `docker-compose.yml`, install the
toolkit (`nvidia-ctk runtime configure ...` on Linux / WSL2), then
`docker compose up -d --force-recreate dev`. Windows Docker Desktop
with WSL2 backend + recent NVIDIA driver exposes GPUs automatically;
older setups need manual WSL kernel updates.
