"""Runtime provenance helpers for reproducible benchmark reports."""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np

import seeingbench


def runtime_provenance(repo_root: Path | None = None) -> dict[str, Any]:
    """Return machine-readable software and repository provenance."""

    root = _repo_root(repo_root)
    git = _git_provenance(root)
    return {
        "seeingbench_version": seeingbench.__version__,
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "numpy_version": np.__version__,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "process_id": os.getpid(),
        "git": git,
    }


def _repo_root(repo_root: Path | None) -> Path:
    if repo_root is not None:
        return repo_root
    return Path(__file__).resolve().parents[3]


def _git_provenance(repo_root: Path) -> dict[str, Any]:
    commit = _git(repo_root, "rev-parse", "HEAD")
    branch = _git(repo_root, "rev-parse", "--abbrev-ref", "HEAD")
    status = _git(repo_root, "status", "--short")
    remote = _git(repo_root, "config", "--get", "remote.origin.url")
    return {
        "available": commit is not None,
        "commit": commit,
        "branch": branch,
        "dirty": None if status is None else bool(status.strip()),
        "status_short": None if status is None else status.splitlines(),
        "origin_url": remote,
    }


def _git(repo_root: Path, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=5.0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()
