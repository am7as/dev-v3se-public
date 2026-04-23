# Container modes — dev vs deployment

Every template supports two container modes. Most of your time is spent
in **dev mode**. Deployment is for shipping a finished artifact to Alvis
or handing it to a collaborator.

## Dev mode (default)

**Code lives on the host; the container only provides the environment.**

```
HOST                                   CONTAINER
my-project/                            /workspace/
  src/my_pkg/...     ────bind-mount──>   src/my_pkg/...
  scripts/...                            scripts/...
  configs/...                            configs/...
  pixi.toml                              pixi.toml
```

You edit `src/my_pkg/__init__.py` on the host with your IDE. The change
is visible inside the container immediately — no rebuild, no restart.
Running `pixi run smoke` inside the container picks it up.

### Docker dev (laptop)

```powershell
docker compose up -d dev
docker compose exec dev pixi run smoke    # iterate
docker compose exec dev bash              # interactive shell
```

`docker-compose.yml` defines `.:/workspace` — your whole project
directory becomes `/workspace` inside the container. Edits on the host
appear instantly inside.

### Apptainer dev (laptop or Alvis)

```bash
apptainer build dev.sif apptainer/dev.def
apptainer run --bind .:/workspace dev.sif pixi run smoke
```

`apptainer/dev.def` is identical to `app.def` except it **does not
`%files`-copy your source into the image**. `--bind .:/workspace` is
the explicit mount at run time.

This is the normal pattern on Alvis: build the dev SIF once, run it
many times with your live code bound in.

## Deployment mode

**Code is baked into the image.** The SIF is a self-contained artifact.

```
my-project-v1.sif                      CONTAINER
└── (everything, including code)   ─>  /workspace/
                                         src/my_pkg/...
                                         scripts/...
                                         configs/...
                                         pixi.toml
                                         .pixi/ (pre-installed env)
```

### When to use deployment mode

- **Reproducible publication**: the SIF you ran your final results from
  should be archived. Dev-mode SIFs depend on whatever was in the bind
  mount at run time, which is not reproducible.
- **Handing off to collaborators**: they get one file.
- **Quota pressure**: when you're close to the 60k-file ceiling, a single
  baked SIF replaces a full Pixi env tree on disk.
- **Production-style batch runs**: no accidental dev-state contamination.

### Building a deployment SIF

```bash
apptainer build my-project-v1.sif apptainer/app.def
```

Inside `app.def`, the `%files` section copies your project into
`/workspace`, and the `%post` section runs `pixi install` so the env is
pre-baked. Running it needs no bind mounts:

```bash
apptainer run --nv my-project-v1.sif pixi run smoke
```

## When you use which

| Situation                          | Mode          |
|------------------------------------|---------------|
| Writing code on laptop             | Docker dev    |
| Debugging on Alvis with live edits | Apptainer dev |
| Final publication run              | Apptainer deployment |
| Shipping to a collaborator         | Apptainer deployment |
| Short iteration / prototyping      | Any dev       |
| Long multi-day Slurm job           | Apptainer deployment (avoids host-side changes mid-run) |

## Which files belong to which mode

| File                    | Used by                           |
|-------------------------|-----------------------------------|
| `docker-compose.yml`    | Docker dev only                   |
| `apptainer/dev.def`     | Apptainer dev (laptop + Alvis)    |
| `apptainer/app.def`     | Apptainer deployment              |
| `pixi.toml` + `pyproject.toml` | Both modes (describe the env) |
| `slurm/*.sbatch`        | Either — they invoke `apptainer run ... dev.sif` or `... app.sif` |
| `.env`                  | Both modes (runtime config)       |

## Caveats

- **SIFs are read-only** once built. Writing to `/workspace/...` inside a
  dev-mode SIF writes to the bound host directory; writing inside a
  deployment SIF silently fails unless you explicitly `--bind` a
  writable path over it.
- **Pixi env inside deployment SIF is sealed**. You cannot
  `pixi add torch` and have it take effect — that would require
  rebuilding. Dev mode is the only place packages can change.
- **Secrets** (API keys) **never** go into deployment SIFs. Always read
  from `.env` via env vars at runtime. Bind your `.env` in:
  ```bash
  apptainer run --nv --bind .env:/workspace/.env my-project-v1.sif ...
  ```
