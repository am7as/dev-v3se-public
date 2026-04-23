"""Claude Code CLI as a subprocess — uses your Claude Pro/Max subscription.

Requires:
  - `claude` binary on PATH (Dockerfile/Apptainer installs it via npm).
  - Host ~/.claude and ~/.claude.json bind-mounted into the container
    (see docker-compose.yml / sbatch examples).
  - You've run `claude login` once on the host (browser flow).
"""
from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any

NAME = "claude_cli"


def _binary() -> str:
    return os.environ.get("CLAUDE_CLI_PATH") or "claude"


def predict(prompt: str, *, model: str | None = None, **kw: Any) -> dict[str, Any]:
    binary = _binary()
    if shutil.which(binary) is None:
        raise RuntimeError(
            f"Claude CLI '{binary}' not found. Install it in the container "
            f"(npm i -g @anthropic-ai/claude-code) or set CLAUDE_CLI_PATH."
        )
    m = model or os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

    # --print = non-interactive; reads prompt from stdin
    proc = subprocess.run(
        [binary, "--print", "--model", m],
        input=prompt, text=True, capture_output=True, check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"claude CLI exited {proc.returncode}: {proc.stderr.strip()}"
        )
    return {
        "text":  proc.stdout.strip(),
        "raw":   {"stdout": proc.stdout, "stderr": proc.stderr},
        "model": m,
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }
