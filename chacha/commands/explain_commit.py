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
)


app = typer.Typer()


@app.command()
def run(
    target: Optional[str] = typer.Argument(
        None,
        help="Commit ref, hash, or negative index (e.g., -1 for HEAD, -2 for previous).",
    ),
    cohesive: Optional[int] = typer.Option(
        None,
        "--cohesive",
        "-c",
        help="Explain last N commits cohesively (combined narrative). If TARGET is provided, uses TARGET as the anchor (inclusive).",
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
        explain_commits_cohesively(target, cohesive, provider)
    else:
        explain_single_commit(target, provider)


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
    patch = get_commit_patch(sha, max_bytes=120_000)

    files_preview = "\n".join(f"- {f}" for f in files[:50])
    if len(files) > 50:
        files_preview += f"\n… (+{len(files) - 50} more)"

    prompt_parts: List[str] = [
        "You are a senior engineer. Explain this Git commit for a code review summary.",
        "",
        "Please produce:",
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
            "Unified Diff (may be truncated):",
            "```diff",
            patch or "(no patch)",
            "```",
        ]
    )
    prompt = "\n".join(prompt_parts)

    response = generate_text(prompt, max_tokens=1800, temperature=0.2)
    box = ui_utils.format_box(
        title="Chacha — Commit Explanation",
        subtitle=f"Provider: {provider}  •  Commit: {sha[:12]}",
        content=response,
    )
    typer.echo(box)


def explain_commits_cohesively(anchor_spec: Optional[str], count: int, provider: str) -> None:
    # Determine anchor commit; default to HEAD
    anchor_sha = resolve_commit_sha(anchor_spec or "-1")
    if not anchor_sha:
        typer.echo(f"❌ Could not resolve commit: {anchor_spec}", err=True)
        raise typer.Exit(code=1)

    newest_to_oldest = rev_list(anchor_sha, count)
    if not newest_to_oldest:
        typer.echo("❌ No commits found for the requested range.", err=True)
        raise typer.Exit(code=1)

    # Oldest -> newest for narrative
    shas = list(reversed(newest_to_oldest))

    # Heuristic patch budget to avoid overlong prompts
    per_commit_patch_budget = max(40_000 // max(1, len(shas)), 10_000)

    sections: List[str] = []
    for i, sha in enumerate(shas, start=1):
        subject = get_commit_subject(sha)
        author = get_commit_author(sha)
        date = get_commit_date(sha)
        files = get_commit_files_changed(sha)
        stats = get_commit_stats(sha)
        patch = get_commit_patch(sha, max_bytes=per_commit_patch_budget)
        sections.extend(
            [
                f"=== Commit {i}/{len(shas)} — {sha[:12]} ===",
                f"Subject: {subject}",
                f"Author: {author}",
                f"Date: {date}",
                "Files:",
                *(f"- {f}" for f in files[:30]),
                "Stats:",
                stats or "(no stats)",
                "Diff (may be truncated):",
                "```diff",
                patch or "(no patch)",
                "```",
                "",
            ]
        )

    system_instructions = [
        "You are a senior engineer. Explain these commits as a cohesive change set.",
        "Focus on the overarching goal, how changes evolve commit-to-commit, and cumulative impact.",
        "",
        "Please produce:",
        "- TL;DR (1-2 sentences) for the overall set",
        "- Narrative: how the set of commits fits together",
        "- Key changes by theme (bulleted)",
        "- Risks across the set",
        "- Tests to add or update covering the whole change",
        "",
        "Commits (oldest to newest):",
        *sections,
    ]

    prompt = "\n".join(system_instructions)
    response = generate_text(prompt, max_tokens=2200, temperature=0.2)
    box = ui_utils.format_box(
        title="Chacha — Cohesive Commit Explanation",
        subtitle=f"Provider: {provider}  •  Commits: {len(shas)} (ending at {shas[-1][:12]})",
        content=response,
    )
    typer.echo(box)


