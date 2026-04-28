"""Google Cloud Storage via rclone.

The container image includes rclone. Configuration is expected to live
in $HOME/.config/rclone/rclone.conf (bind-mount it).

Usage pattern:
    from data_multi.sources import gcs
    path = gcs.mount()        # returns a Path under /tmp/gcs-mount
    # then read files from path/
    gcs.unmount()
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

NAME = "gcs"

_MOUNT_POINT = Path("/tmp/gcs-mount")


def resolve(dataset: str | None = None) -> Path:
    """Return the GCS mount point. Does NOT mount — caller uses mount()."""
    p = _MOUNT_POINT
    if dataset:
        p = p / dataset
    return p


def mount() -> Path:
    remote = os.environ.get("GCS_RCLONE_REMOTE")
    path   = os.environ.get("GCS_RCLONE_PATH", "")
    if not remote:
        raise RuntimeError("Set GCS_RCLONE_REMOTE in .env (e.g., 'waymo:open-v1')")
    _MOUNT_POINT.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["rclone", "mount", f"{remote}:{path}", str(_MOUNT_POINT),
         "--daemon", "--read-only", "--vfs-cache-mode", "off"],
        check=True,
    )
    return _MOUNT_POINT


def unmount() -> None:
    subprocess.run(["fusermount", "-u", str(_MOUNT_POINT)], check=False)
