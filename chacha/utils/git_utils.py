"""Git utilities (safe, minimal subprocess wrappers)."""

from __future__ import annotations

import subprocess
from typing import List, Optional


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


def _is_negative_int(text: str) -> bool:
    try:
        return int(text) < 0
    except Exception:
        return False


def _negative_index_to_rev(text: str) -> Optional[str]:
    """Map '-1' -> 'HEAD', '-2' -> 'HEAD~1', '-3' -> 'HEAD~2', etc."""
    try:
        n = int(text)
    except Exception:
        return None
    if n >= 0:
        return None
    k = abs(n)
    if k == 1:
        return "HEAD"
    return f"HEAD~{k-1}"


def resolve_commit_sha(spec: str) -> Optional[str]:
    """Resolve a commit spec (hash/ref or negative index) to a full SHA."""
    spec = (spec or "").strip()
    if not spec:
        spec = "-1"
    if _is_negative_int(spec):
        rev = _negative_index_to_rev(spec)
        if not rev:
            return None
        sha = _run_git(["rev-parse", rev])
        return sha or None
    # Assume it's a hash or ref
    sha = _run_git(["rev-parse", spec])
    return sha or None


def rev_list(anchor: str, count: int) -> list[str]:
    """Return up to 'count' SHAs reachable from 'anchor' (newest first)."""
    if count <= 0:
        return []
    out = _run_git(["rev-list", "--max-count", str(count), anchor])
    return [line for line in out.splitlines() if line]


def get_commit_subject(sha: str) -> str:
    return _run_git(["show", "-s", "--pretty=%s", sha]) or ""


def get_commit_author(sha: str) -> str:
    return _run_git(["show", "-s", "--pretty=%an <%ae>", sha]) or ""


def get_commit_date(sha: str) -> str:
    # --date=iso-strict-local gives readable local time
    return _run_git(["show", "-s", "--date=iso-strict-local", "--pretty=%ad", sha]) or ""


def get_commit_body(sha: str) -> str:
    return _run_git(["show", "-s", "--pretty=%b", sha]) or ""


def get_commit_files_changed(sha: str) -> list[str]:
    out = _run_git(["show", "--name-only", "--pretty=format:", sha])
    files: list[str] = []
    for line in out.splitlines():
        if line.strip():
            files.append(line.strip())
    return files


def get_commit_stats(sha: str) -> str:
    # Summary statistics (files changed, insertions, deletions)
    stat = _run_git(["show", "--stat", "--oneline", sha])
    return stat or ""


def get_commit_patch(sha: str, max_bytes: int = 200_000) -> str:
    """Return unified diff patch for a commit; truncate if too large."""
    patch = _run_git(["show", "--format=format:", "--patch", sha])
    if not patch:
        return ""
    if len(patch) > max_bytes:
        head = patch[: max_bytes - 200]
        tail_note = f"\n\n--- [Diff truncated to {max_bytes} bytes] ---"
        return head + tail_note
    return patch


