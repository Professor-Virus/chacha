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


def get_staged_diff() -> str:
    """Get the diff of all staged files."""
    return _run_git(["diff", "--cached"]) or ""


def get_unstaged_diff() -> str:
    """Get the diff of all unstaged files."""
    return _run_git(["diff"]) or ""


def get_all_changes_diff() -> str:
    """Get the diff of all changes (staged + unstaged)."""
    staged = get_staged_diff()
    unstaged = get_unstaged_diff()
    if staged and unstaged:
        return f"=== STAGED CHANGES ===\n{staged}\n\n=== UNSTAGED CHANGES ===\n{unstaged}"
    return staged or unstaged


def get_staged_files() -> list[str]:
    """Get list of staged files."""
    out = _run_git(["diff", "--cached", "--name-only"])
    if not out:
        return []
    return [f.strip() for f in out.splitlines() if f.strip()]


# def get_all_changed_files() -> dict[str, str]:
#     """Get all changed files with their status.
    
#     Returns:
#         Dictionary mapping filename to status:
#         - 'staged': File is staged
#         - 'unstaged': File is modified but not staged
#         - 'both': File has both staged and unstaged changes
#     """
#     out = _run_git(["status", "--porcelain"])
#     files: dict[str, str] = {}
    
#     for line in out.splitlines():
#         if not line or len(line) < 3:
#             continue
        
#         status = line[:2]
#         # Git status format: "XY filename" - split after the 2-char status
#         # Use split with maxsplit=1 to handle filenames with spaces
#         parts = line[2:].strip().split(maxsplit=1)
#         if len(parts) < 2:
#             continue
        
#         filename = parts[1].strip()
        
#         staged = status[0] in ["M", "A", "D", "R", "C"]
#         unstaged = status[1] in ["M", "A", "D", "R", "?"]
        
#         if staged and unstaged:
#             files[filename] = "both"
#         elif staged:
#             files[filename] = "staged"
#         elif unstaged:
#             files[filename] = "unstaged"
    
#     return files


def stage_files() -> tuple[bool, str]:
    """Stage the given files.
    
    Args:
        files: List of file paths to stage
        
    Returns:
        Tuple of (success: bool, error_message: str)
        If successful, error_message will be empty
    """
    files = get_changed_files()
    if not files:
        return True, ""
    
    result = subprocess.run(
        ["git", "add", *files],
        capture_output=True,
        text=True,
    )
    
    if result.returncode == 0:
        return True, ""
    else:
        error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
        return False, error_msg


def get_upstream_and_remote_branches() -> list[str]:
    """Get upstream branch first (if defined), then all remote branches.
    
    Returns:
        List of branch names with upstream branch first (if exists),
        followed by all remote branches.
    """
    branches: list[str] = []
    
    # Get upstream branch (if exists)
    upstream = _run_git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    if upstream:
        # Format: origin/branch-name -> just branch-name
        if "/" in upstream:
            upstream_branch = upstream.split("/", 1)[1]
            branches.append(upstream_branch)
    
    # Get all remote branches
    remote_branches_out = _run_git(["branch", "-r"])
    if remote_branches_out:
        seen = set(branches)  # Track what we've already added
        for line in remote_branches_out.splitlines():
            line = line.strip()
            if not line or "->" in line:  # Skip HEAD pointer
                continue
            # Format: origin/branch-name -> extract branch-name
            if "/" in line:
                branch_name = line.split("/", 1)[1]
                if branch_name not in seen:
                    branches.append(branch_name)
                    seen.add(branch_name)
    
    return branches

