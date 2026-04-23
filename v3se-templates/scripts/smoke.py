"""Golden-path smoke test: collect runtime info and write a manifest.

Run:
    pixi run smoke

What happens:
    1. Collect CPU + GPU + runtime + env info.
    2. Print a short human summary.
    3. Write the full manifest as JSON to $RESULTS_DIR/manifest-<ts>.json.

Exit code is 0 on success. Non-zero means the template's plumbing is broken.
"""
from __future__ import annotations

import sys

from __PACKAGE_NAME__ import manifest as _manifest


def _human_summary(m: dict) -> None:
    cpu = m["cpu"]
    gpus = m["gpu"]
    rt = m["runtime"]
    print(f"host         : {rt['hostname']}")
    print(f"python       : {rt['python_version']}  ({rt['python_exe']})")
    print(f"container    : {rt['in_container']}")
    if rt["in_slurm"]:
        print(f"slurm job    : {rt['slurm_job_id']} on {rt['slurm_node']} ({rt['slurm_partition']})")
    print(f"cpus         : {cpu['logical_cores']} logical ({cpu['system']} {cpu['release']}, {cpu['machine']})")
    if gpus:
        print(f"gpus         : {len(gpus)} via {gpus[0]['source']}")
        for g in gpus:
            print(f"  [{g['index']}] {g['name']}  ({g['memory_mib']} MiB)")
    else:
        print("gpus         : none detected")
    print(f"data_dir     : {m['paths']['data_dir']}")
    print(f"results_dir  : {m['paths']['results_dir']}")
    print(f"models_dir   : {m['paths']['models_dir']}")


def main() -> int:
    m = _manifest.build_manifest()
    _human_summary(m)
    out = _manifest.write_manifest(m)
    print()
    print(f"manifest     : {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
