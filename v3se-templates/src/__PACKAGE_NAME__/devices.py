"""Collect device info (CPUs, GPUs, memory, env, runtime)."""
from __future__ import annotations

import os
import platform
import shutil
import socket
import subprocess
import sys
from typing import Any


def _cpu_info() -> dict[str, Any]:
    return {
        "logical_cores": os.cpu_count() or 0,
        "machine":       platform.machine(),
        "processor":     platform.processor(),
        "system":        platform.system(),
        "release":       platform.release(),
    }


def _gpu_info_via_nvidia_smi() -> list[dict[str, Any]]:
    """Try nvidia-smi first — works inside containers with --nv even if
    torch isn't installed. Returns [] if the binary is missing or errors."""
    if shutil.which("nvidia-smi") is None:
        return []
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError):
        return []
    gpus: list[dict[str, Any]] = []
    for line in out.strip().splitlines():
        fields = [f.strip() for f in line.split(",")]
        if len(fields) != 4:
            continue
        idx, name, mem_mib, driver = fields
        gpus.append({
            "index":        int(idx),
            "name":         name,
            "memory_mib":   int(mem_mib),
            "driver_version": driver,
            "source":       "nvidia-smi",
        })
    return gpus


def _gpu_info_via_torch() -> list[dict[str, Any]]:
    """Fall back to torch.cuda if it's available (reports what the
    program actually sees, not what the host has)."""
    try:
        import torch  # noqa: PLC0415 (deliberate late import)
    except ImportError:
        return []
    if not torch.cuda.is_available():
        return []
    gpus: list[dict[str, Any]] = []
    for i in range(torch.cuda.device_count()):
        props = torch.cuda.get_device_properties(i)
        gpus.append({
            "index":      i,
            "name":       props.name,
            "memory_mib": int(props.total_memory // (1024 * 1024)),
            "cuda_cap":   f"{props.major}.{props.minor}",
            "source":     "torch",
        })
    return gpus


def gpu_info() -> list[dict[str, Any]]:
    """Prefer nvidia-smi (always matches the hardware); fall back to torch."""
    gpus = _gpu_info_via_nvidia_smi()
    if gpus:
        return gpus
    return _gpu_info_via_torch()


def runtime_info() -> dict[str, Any]:
    return {
        "hostname":        socket.gethostname(),
        "python_version":  sys.version.split()[0],
        "python_exe":      sys.executable,
        "in_slurm":        bool(os.environ.get("SLURM_JOB_ID")),
        "slurm_job_id":    os.environ.get("SLURM_JOB_ID", ""),
        "slurm_node":      os.environ.get("SLURMD_NODENAME", ""),
        "slurm_partition": os.environ.get("SLURM_JOB_PARTITION", ""),
        "in_container":    os.path.exists("/.dockerenv") or os.path.exists("/.singularity.d"),
    }


def relevant_env() -> dict[str, str]:
    """Subset of env vars the template cares about."""
    keys = [
        "DATA_DIR", "RESULTS_DIR", "MODELS_DIR", "WORKSPACE_DIR",
        "HF_HOME", "TRANSFORMERS_CACHE",
        "CUDA_VISIBLE_DEVICES",
        "LOG_LEVEL",
    ]
    return {k: os.environ.get(k, "") for k in keys}


def collect() -> dict[str, Any]:
    return {
        "cpu":     _cpu_info(),
        "gpu":     gpu_info(),
        "runtime": runtime_info(),
        "env":     relevant_env(),
    }
