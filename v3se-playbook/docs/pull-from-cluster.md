# Pull: results and artefacts back to laptop

Mirror of the push side. Small results on Cephyr, big ones on Mimer.

## Pulling small results from Cephyr

Job `.out` / `.err` files, manifest JSONs, summary CSVs — small
text artefacts that live next to the code:

**PowerShell:**

```powershell
rsync -avh --progress `
  <cid>@vera2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/<project>/results/ `
  .\results\
```

**bash / zsh:**

```bash
rsync -avh --progress \
  <cid>@vera2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/<project>/results/ \
  ./results/
```

## Pulling big artefacts from Mimer

Trained weights, checkpoints, evaluation dumps, wandb logs:

**PowerShell:**

```powershell
rsync -avh --progress `
  <cid>@vera2.c3se.chalmers.se:/mimer/NOBACKUP/groups/<naiss-id>/<cid>/<project>/checkpoints/ `
  .\checkpoints\
```

**bash / zsh:**

```bash
rsync -avh --progress \
  <cid>@vera2.c3se.chalmers.se:/mimer/NOBACKUP/groups/<naiss-id>/<cid>/<project>/checkpoints/ \
  ./checkpoints/
```

## Selective pulls

`rsync` supports include/exclude patterns:

```bash
rsync -avh --progress \
  --include='*.json' --include='*.csv' --exclude='*' \
  <cid>@vera2.c3se.chalmers.se:/cephyr/users/<cid>/Alvis/<project>/results/ \
  ./results/
```

And `--remove-source-files` to move (not copy):

```bash
rsync -avh --progress --remove-source-files \
  <cid>@vera2.c3se.chalmers.se:/mimer/NOBACKUP/groups/<naiss-id>/<cid>/<project>/wandb/ \
  ./wandb/
```

Useful when Mimer is close to quota — pull the old runs off.

## One-shot `.sif` transfer

Large SIFs go over `scp` (or rsync). Use the Mimer path to store
(they're big) unless the SIF is for your team's shared use in which
case bake it into `.../<naiss-id>/shared/sifs/`:

**PowerShell & bash:**

```bash
scp ./my-model.sif <cid>@vera2.c3se.chalmers.se:/mimer/NOBACKUP/groups/<naiss-id>/<cid>/sifs/
```

## Summary scripts (optional)

A project can ship a `_shared/scripts/sync-from-cephyr.sh` /
`sync-from-mimer.sh` mirroring the push scripts. The patterns are
identical; only source and destination flip.
