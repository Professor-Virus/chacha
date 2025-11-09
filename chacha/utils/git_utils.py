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


def get_commit_parents(sha: str) -> list[str]:
    """Return parent SHAs for a commit (may be empty for root)."""
    out = _run_git(["show", "-s", "--pretty=%P", sha])
    parts = (out or "").split()
    return [p for p in parts if p]


def get_empty_tree_sha() -> str:
    """Return the SHA of the empty tree object."""
    sha = _run_git(["hash-object", "-t", "tree", "/dev/null"])
    # Fallback to the well-known empty tree SHA if command fails
    return sha or "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def get_cumulative_diff_patch(base: str, anchor: str, max_bytes: int = 120_000) -> str:
    """Return unified diff for the range base..anchor with rename/copy detection."""
    patch = _run_git(
        ["diff", "--patch", "--find-renames", "--find-copies", f"{base}..{anchor}"]
    )
    if not patch:
        return ""
    if len(patch) > max_bytes:
        head = patch[: max_bytes - 200]
        tail_note = f"\n\n--- [Cumulative diff truncated to {max_bytes} bytes] ---"
        return head + tail_note
    return patch


def get_cumulative_diff_shortstat(base: str, anchor: str) -> str:
    """Return shortstat summary (files changed, insertions, deletions) for base..anchor."""
    return _run_git(["diff", "--shortstat", f"{base}..{anchor}"]) or ""


def get_cumulative_diff_numstat(base: str, anchor: str) -> list[tuple[int, int, str]]:
    """Return per-file added/deleted counts for base..anchor."""
    out = _run_git(["diff", "--numstat", f"{base}..{anchor}"])
    rows: list[tuple[int, int, str]] = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        adds_s, dels_s, path = parts
        try:
            adds = int(adds_s) if adds_s.isdigit() else 0
        except Exception:
            adds = 0
        try:
            dels = int(dels_s) if dels_s.isdigit() else 0
        except Exception:
            dels = 0
        rows.append((adds, dels, path))
    return rows


def split_patch_by_file(patch: str) -> list[tuple[str, str]]:
    """Split a unified diff into (path, chunk) pairs using 'diff --git a/ b/' markers."""
    if not patch:
        return []
    results: list[tuple[str, str]] = []
    current_lines: list[str] = []
    current_path: str = ""
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            # Flush previous
            if current_lines and current_path:
                results.append((current_path, "\n".join(current_lines)))
            # Parse path
            parts = line.strip().split()
            # Format: diff --git a/path b/path
            if len(parts) >= 4 and parts[-2].startswith("a/") and parts[-1].startswith("b/"):
                path_a = parts[-2][2:]
                path_b = parts[-1][2:]
                # Prefer b/ path, fallback to a/
                current_path = path_b or path_a
            else:
                current_path = ""
            current_lines = [line]
        else:
            current_lines.append(line)
    if current_lines and current_path:
        results.append((current_path, "\n".join(current_lines)))
    return results

