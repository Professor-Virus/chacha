"""Git utilities (safe, minimal subprocess wrappers)."""

from __future__ import annotations

import subprocess
from typing import List


def _run_git(args: List[str]) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def get_changed_files() -> list[str]:
    out = _run_git(["status", "--porcelain"])
    files: list[str] = []
    for line in out.splitlines():
        if not line:
            continue
        # format: "XY filename"
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            files.append(parts[1])
    return files


def get_last_commit_message() -> str:
    return _run_git(["log", "-1", "--pretty=%B"]) or ""


