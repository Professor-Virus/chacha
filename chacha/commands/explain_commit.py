"""Explain Git commit(s) with AI."""

from __future__ import annotations

import typer
from typing import Optional, List

from chacha.utils import ui_utils
from chacha.utils.ai_utils import generate_text, get_provider
from chacha.utils.git_utils import (
    resolve_commit_sha,
    rev_list,
    get_commit_subject,
    get_commit_author,
    get_commit_date,
    get_commit_body,
    get_commit_files_changed,
    get_commit_stats,
    get_commit_patch,
    get_commit_parents,
    get_empty_tree_sha,
    get_cumulative_diff_patch,
    get_cumulative_diff_shortstat,
    get_cumulative_diff_numstat,
)


app = typer.Typer(
    invoke_without_command=True,
    help=(
        "Two modes:\n"
        "- Single commit: chacha explain commit [TARGET] or --spec <ref>\n"
        "- Cohesive N commits (anchored to HEAD): chacha explain commit -c N\n"
        "Do NOT combine --cohesive with TARGET/--spec.\n"
        "Tip: For negative TARGET (e.g., -2), use `--` (e.g., `... -- -2`) or `--spec -2`."
    ),
)


@app.callback()
def main(
    target: Optional[str] = typer.Argument(
        None,
        help="Commit ref, hash, or negative index (e.g., -1 for HEAD, -2 for previous).",
    ),
    spec: Optional[str] = typer.Option(
        None,
        "--spec",
        help="Commit ref, hash, or negative index explicitly as an option (useful for negative values without `--`).",
    ),
    cohesive: Optional[int] = typer.Option(
        None,
        "--cohesive",
        "-c",
        help="Explain last N commits cohesively (combined narrative), anchored to HEAD. Do not combine with TARGET/--spec.",
    ),
) -> None:
    """Explain one commit by default, or N commits cohesively with -c/--cohesive."""
    try:
        provider = get_provider()
    except Exception:
        provider = "unknown"

    if cohesive and cohesive <= 0:
        typer.echo("❌ --cohesive must be a positive integer.", err=True)
        raise typer.Exit(code=1)

    if cohesive:
        # Enforce mutually exclusive modes: cohesive ignores TARGET/--spec
        if target is not None or spec is not None:
            typer.echo("❌ Do not combine --cohesive with TARGET/--spec. Use one mode at a time.", err=True)
            raise typer.Exit(code=2)
        explain_commits_cohesively(None, cohesive, provider)
    else:
        effective_target = spec if spec is not None else target
        explain_single_commit(effective_target, provider)


def _truncate(text: str, limit: int) -> str:
    if not isinstance(text, str):
        return ""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def explain_single_commit(target: Optional[str], provider: str) -> None:
    commit_spec = target or "-1"
    sha = resolve_commit_sha(commit_spec)
    if not sha:
        typer.echo(f"❌ Could not resolve commit: {commit_spec}", err=True)
        raise typer.Exit(code=1)

    subject = get_commit_subject(sha)
    author = get_commit_author(sha)
    date = get_commit_date(sha)
    body = get_commit_body(sha)
    files = get_commit_files_changed(sha)
    stats = get_commit_stats(sha)
    patch = get_commit_patch(sha, max_bytes=80_000)

    files_preview = "\n".join(f"- {f}" for f in files[:50])
    if len(files) > 50:
        files_preview += f"\n… (+{len(files) - 50} more)"

    prompt_parts: List[str] = [
        "You are a senior engineer. Explain this Git commit for a code review summary.",
        "",
        "Please produce (keep under ~400 words):",
        "- TL;DR (1-2 sentences)",
        "- Key changes (bulleted)",
        "- Potential risks or regressions",
        "- Tests to add or update",
        "",
        "Commit Metadata:",
        f"- SHA: {sha}",
        f"- Author: {author}",
        f"- Date: {date}",
        f"- Subject: {subject}",
    ]
    if body.strip():
        prompt_parts.extend(["- Body:", body.strip()])
    prompt_parts.extend(
        [
            "",
            "Files Changed:",
            files_preview or "(none listed)",
            "",
            "Stats:",
            stats or "(no stats)",
            "",
            "Unified Diff (trimmed, may be truncated):",
            "```diff",
            patch or "(no patch)",
            "```",
        ]
    )
    prompt = "\n".join(prompt_parts)

    response = generate_text(prompt, max_tokens=1600, temperature=0.2)
    # Fallback if provider returned no text
    if isinstance(response, str) and response.strip().startswith("⚠️"):
        compact = "\n".join(
            [
                "Explain this commit succinctly (<=200 words).",
                f"SHA: {sha}",
                f"Subject: {subject}",
                "Files:",
                files_preview or "(none)",
                "Stats:",
                stats or "(no stats)",
            ]
        )
        response = generate_text(compact, max_tokens=800, temperature=0.2)
    box = ui_utils.format_box(
        title="Chacha — Commit Explanation",
        subtitle=f"Provider: {provider}  •  Commit: {sha[:12]}",
        content=response,
    )
    typer.echo(box)


def explain_commits_cohesively(anchor_spec: Optional[str], count: int, provider: str) -> None:
    # Pairwise mode: explain the delta between HEAD~N and HEAD~(N-1) (oldest pair),
    # minimizing tokens by sending only that delta plus brief commit context.
    if count < 1:
        typer.echo("❌ --cohesive N must be >= 1.", err=True)
        raise typer.Exit(code=1)

    # Resolve the pair: older = HEAD~N, newer = HEAD~(N-1) (newer is closer to HEAD)
    older_expr = f"HEAD~{count}"
    newer_expr = f"HEAD~{max(count - 1, 0)}"
    older_sha = resolve_commit_sha(older_expr)
    newer_sha = resolve_commit_sha(newer_expr)
    if not older_sha or not newer_sha:
        typer.echo(f"❌ Not enough history to resolve {older_expr} or {newer_expr}.", err=True)
        raise typer.Exit(code=1)

    older_subject = get_commit_subject(older_sha)
    newer_subject = get_commit_subject(newer_sha)

    # Delta between the two commits
    shortstat = get_cumulative_diff_shortstat(older_sha, newer_sha)
    numstat_rows = get_cumulative_diff_numstat(older_sha, newer_sha)
    ranked = sorted(numstat_rows, key=lambda r: (r[0] + r[1]), reverse=True)
    top_files = ranked[:12]
    top_files_lines = [
        f"- {adds + dels:>4} lines changed (+{adds}/-{dels})  {path}"
        for adds, dels, path in top_files
    ] or ["(no files)"]
    patch = get_cumulative_diff_patch(older_sha, newer_sha, max_bytes=50_000)

    prompt = "\n".join(
        [
            "You are a senior engineer. Provide a cohesive explanation (<=250 words) for the net changes between two adjacent commits.",
            "",
            f"Pair: {older_sha[:12]} → {newer_sha[:12]}",
            f"- Older subject: {older_subject}",
            f"- Newer subject: {newer_subject}",
            "",
            "Shortstat:",
            shortstat or "(none)",
            "",
            "Top changed files by churn:",
            *top_files_lines,
            "",
            "Unified diff (trimmed):",
            "```diff",
            patch or "(no patch)",
            "```",
            "",
            "Please produce:",
            "- TL;DR (1-2 sentences)",
            "- Key changes by theme (bulleted)",
            "- Risks/regressions to watch for",
            "- Tests to add or update",
        ]
    )
    response = generate_text(prompt, max_tokens=700, temperature=0.2)
    if isinstance(response, str) and response.strip().startswith("⚠️"):
        # Fallback without diff
        prompt_no_diff = "\n".join(
            [
                "Explain this adjacent-commit delta briefly (<=180 words).",
                f"Pair: {older_sha[:12]} → {newer_sha[:12]}",
                f"- Older subject: {older_subject}",
                f"- Newer subject: {newer_subject}",
                "",
                "Shortstat:",
                shortstat or "(none)",
                "",
                "Top changed files:",
                *top_files_lines,
            ]
        )
        response = generate_text(prompt_no_diff, max_tokens=420, temperature=0.2)
    if isinstance(response, str) and response.strip().startswith("⚠️"):
        # Deterministic fallback
        lines: List[str] = []
        lines.append(f"TL;DR: Changes from {older_sha[:12]} → {newer_sha[:12]}")
        lines.append(f"- Older: {older_subject}")
        lines.append(f"- Newer: {newer_subject}")
        lines.append("")
        lines.append("Top changed files:")
        lines.extend(top_files_lines)
        response = "\n".join(lines)

    box = ui_utils.format_box(
        title="Chacha — Cohesive Commit Explanation",
        subtitle=f"Provider: {provider}  •  Pair: {older_sha[:12]} → {newer_sha[:12]}",
        content=response,
    )
    typer.echo(box)


