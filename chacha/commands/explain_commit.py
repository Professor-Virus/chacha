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


app = typer.Typer(invoke_without_command=True, help="Explain one commit by default, or N cohesively via -c/--cohesive.\nTip: To pass a negative target (e.g., -2), either use `--` before it (e.g., `chacha explain commit -- -2`) or pass via `--spec -2`.")


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

    effective_target = spec if spec is not None else target

    if cohesive:
        explain_commits_cohesively(effective_target, cohesive, provider)
    else:
        explain_single_commit(effective_target, provider)


def _truncate(text: str, limit: int) -> str:
    if not isinstance(text, str):
        return ""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _split_patch_by_file(patch: str) -> List[str]:
    """Split a unified diff into per-file chunks using 'diff --git' delimiters."""
    if not patch:
        return []
    parts: List[str] = []
    current: List[str] = []
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            if current:
                parts.append("\n".join(current))
                current = []
        current.append(line)
    if current:
        parts.append("\n".join(current))
    return parts


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
    patch = get_commit_patch(sha, max_bytes=30_000)

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

    response = generate_text(prompt, max_tokens=1200, temperature=0.2)
    # Fallback if provider returned no text
    if isinstance(response, str) and response.strip().startswith("⚠️"):
        compact = "\n".join(
            [
                "Explain this commit succinctly (<=180 words).",
                f"SHA: {sha}",
                f"Subject: {subject}",
                "Files:",
                files_preview or "(none)",
                "Stats:",
                stats or "(no stats)",
            ]
        )
        response = generate_text(compact, max_tokens=500, temperature=0.2)
        # If compact also fails, perform per-file mini-summaries and synthesize
        if isinstance(response, str) and response.strip().startswith("⚠️"):
            per_file_sections: List[str] = []
            file_patches = _split_patch_by_file(patch)
            max_files = 10
            for idx, file_diff in enumerate(file_patches[:max_files], start=1):
                file_prompt = "\n".join(
                    [
                        "Summarize the changes in this file (<=80 words) with bullets for key edits:",
                        "```diff",
                        _truncate(file_diff, 6000),
                        "```",
                    ]
                )
                file_summary = generate_text(file_prompt, max_tokens=220, temperature=0.2)
                # Avoid surfacing provider warnings inline
                if isinstance(file_summary, str) and file_summary.strip().startswith("⚠️"):
                    file_summary = "(summary unavailable due to model limits)"
                per_file_sections.append(f"File {idx}:\n{file_summary}")

            # Synthesize final from per-file summaries
            synth_prompt = "\n".join(
                [
                    "Create a concise commit explanation (<=220 words) using these per-file summaries.",
                    "Include: TL;DR, Key changes, Risks, Tests.",
                    "",
                    "\n\n---\n\n".join(per_file_sections),
                ]
            )
            synthesized = generate_text(synth_prompt, max_tokens=360, temperature=0.2)
            if isinstance(synthesized, str) and synthesized.strip().startswith("⚠️"):
                # Fall back to just showing the per-file summaries
                response = "\n\n".join(
                    [
                        "Commit explanation synthesized from per-file summaries (model output limited):",
                        "",
                        "\n\n---\n\n".join(per_file_sections),
                    ]
                )
            else:
                response = synthesized
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

    # Step 1: Summarize each commit individually with small diff budget
    per_commit_patch_budget = 10_000
    per_commit_summaries: List[str] = []
    for i, sha in enumerate(shas, start=1):
        subject = get_commit_subject(sha)
        author = get_commit_author(sha)
        date = get_commit_date(sha)
        files = get_commit_files_changed(sha)
        stats = get_commit_stats(sha)
        patch = get_commit_patch(sha, max_bytes=per_commit_patch_budget)
        files_preview = "\n".join(f"- {f}" for f in files[:30])
        commit_prompt = "\n".join(
            [
                "Summarize this commit for a code review (<=200 words):",
                f"- SHA: {sha}",
                f"- Subject: {subject}",
                f"- Author: {author}",
                f"- Date: {date}",
                "Files:",
                files_preview or "(none)",
                "Stats:",
                stats or "(no stats)",
                "Diff (may be truncated):",
                "```diff",
                patch or "(no patch)",
                "```",
                "",
                "Output format:",
                "- TL;DR:",
                "- Key changes:",
                "- Risks:",
                "- Tests:",
            ]
        )
        summary = generate_text(commit_prompt, max_tokens=500, temperature=0.2)
        if isinstance(summary, str) and summary.strip().startswith("⚠️"):
            compact_commit_prompt = "\n".join(
                [
                    "Summarize this commit briefly (<=100 words):",
                    f"SHA: {sha}",
                    f"Subject: {subject}",
                    "Files:",
                    files_preview or "(none)",
                    "Stats:",
                    stats or "(no stats)",
                ]
            )
            summary = generate_text(compact_commit_prompt, max_tokens=240, temperature=0.2)
        # Keep each per-commit summary short to avoid MAX_TOKENS in the final pass
        per_commit_summaries.append(f"Commit {i}/{len(shas)} {sha[:12]} — {subject}\n{_truncate(summary, 600)}")

    # Step 2: Produce a cohesive narrative from the per-commit summaries
    joined_summaries = "\n\n---\n\n".join(per_commit_summaries)
    final_prompt = "\n".join(
        [
            "You are a senior engineer. Explain these commits as a cohesive change set (<=350 words).",
            "Focus on the overarching goal, how changes evolve commit-to-commit, and cumulative impact.",
            "",
            "Please produce:",
            "- TL;DR (1-2 sentences) for the overall set",
            "- Narrative: how the set of commits fits together",
            "- Key changes by theme (bulleted)",
            "- Risks across the set",
            "- Tests to add or update covering the whole change",
            "",
            "Per-commit summaries:",
            joined_summaries,
        ]
    )
    response = generate_text(final_prompt, max_tokens=800, temperature=0.2)
    # Fallback: if still no text, emit a minimal cohesive summary locally
    if isinstance(response, str) and response.strip().startswith("⚠️"):
        header = [
            "Overall cohesive narrative could not be generated due to model token limits.",
            "Showing per-commit summaries instead:",
            "",
        ]
        response = _truncate("\n".join(header) + joined_summaries, 8000)
    box = ui_utils.format_box(
        title="Chacha — Cohesive Commit Explanation",
        subtitle=f"Provider: {provider}  •  Commits: {len(shas)} (ending at {shas[-1][:12]})",
        content=response,
    )
    typer.echo(box)


