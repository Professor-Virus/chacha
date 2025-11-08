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
    # True cohesive mode: cumulative diff from HEAD~N .. HEAD, with commit subjects context.
    if count < 1:
        typer.echo("❌ --cohesive N must be >= 1.", err=True)
        raise typer.Exit(code=1)

    anchor_sha = resolve_commit_sha("HEAD")
    if not anchor_sha:
        typer.echo("❌ Could not resolve HEAD.", err=True)
        raise typer.Exit(code=1)

    base_expr = f"HEAD~{count}"
    base_sha = resolve_commit_sha(base_expr) or get_empty_tree_sha()

    # Context commits (oldest -> newest)
    newest_to_oldest = rev_list(anchor_sha, count)
    shas = list(reversed(newest_to_oldest)) if newest_to_oldest else []
    subjects = [get_commit_subject(sha) for sha in shas]
    subjects_bullets = "\n".join(
        f"- {i+1}/{len(shas)} {shas[i][:12]} — {subjects[i]}" for i in range(len(shas))
    ) or "(no subjects)"

    # Cumulative stats and top files
    shortstat = get_cumulative_diff_shortstat(base_sha, anchor_sha)
    numstat_rows = get_cumulative_diff_numstat(base_sha, anchor_sha)
    ranked = sorted(numstat_rows, key=lambda r: (r[0] + r[1]), reverse=True)
    top_files = ranked[:15]
    top_files_lines = [
        f"- {adds + dels:>4} lines changed (+{adds}/-{dels})  {path}"
        for adds, dels, path in top_files
    ] or ["(no files)"]

    # Cumulative diff (trimmed)
    cumulative_patch = get_cumulative_diff_patch(base_sha, anchor_sha, max_bytes=60_000)

    prompt = "\n".join(
        [
            "You are a senior engineer. Explain these commits as a cohesive change set (<=350 words).",
            "Focus on the overarching goal, how changes evolve across the set, and net outcomes.",
            "",
            f"Commit range: {base_sha[:12]}..{anchor_sha[:12]} (last {count} commits)",
            "",
            "Commits (oldest → newest):",
            subjects_bullets,
            "",
            "Cumulative shortstat:",
            shortstat or "(none)",
            "",
            "Top changed files by churn:",
            *top_files_lines,
            "",
            "Unified cumulative diff (trimmed):",
            "```diff",
            cumulative_patch or "(no patch)",
            "```",
            "",
            "Please produce:",
            "- TL;DR (1-2 sentences)",
            "- Key changes by theme (bulleted)",
            "- Risks and potential regressions",
            "- Tests to add or update",
        ]
    )
    response = generate_text(prompt, max_tokens=1100, temperature=0.2)
    if isinstance(response, str) and response.strip().startsWith("⚠️"):
        prompt_no_diff = "\n".join(
            [
                "Explain this cohesive set briefly (<=250 words).",
                f"Commit range: {base_sha[:12]}..{anchor_sha[:12]} (last {count} commits)",
                "",
                "Commits:",
                subjects_bullets,
                "",
                "Cumulative shortstat:",
                shortstat or "(none)",
                "",
                "Top changed files:",
                *top_files_lines,
            ]
        )
        response = generate_text(prompt_no_diff, max_tokens=600, temperature=0.2)
    if isinstance(response, str) and response.strip().startswith("⚠️"):
        tldr_subjects = "; ".join(subjects[:4]) + ("; …" if len(subjects) > 4 else "")
        lines: List[str] = []
        lines.append(f"TL;DR: {count} commits — {tldr_subjects}")
        lines.append("")
        lines.append("Key changes (top files):")
        lines.extend(top_files_lines)
        lines.append("")
        lines.append("Note: Cohesive LLM summary unavailable due to model limits.")
        response = "\n".join(lines)

    box = ui_utils.format_box(
        title="Chacha — Cohesive Commit Explanation",
        subtitle=f"Provider: {provider}  •  Commits: {count} (range {base_sha[:12]}..{anchor_sha[:12]})",
        content=response,
    )
    typer.echo(box)


