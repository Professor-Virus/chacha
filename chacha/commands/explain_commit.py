"""Explain Git commit(s) with AI."""

from __future__ import annotations

import os
import typer
from typing import Optional, List
import re

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
    split_patch_by_file,
    get_commit_numstat,
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

def _truncate_words(text: str, max_words: int) -> str:
    if not isinstance(text, str):
        return ""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + " …"

def _estimate_tokens(text: str) -> int:
    # Rough heuristic: ~1.3 tokens per word
    if not isinstance(text, str) or not text:
        return 0
    return int(len(text.split()) * 1.3)

# Token budgets (overridable via env)
MAX_PROMPT_TOKENS = int(os.getenv("CHACHA_MAX_PROMPT_TOKENS", "6000"))
MAX_SUMMARY_TOKENS = int(os.getenv("CHACHA_MAX_SUMMARY_TOKENS", "1500"))

def _sanitize_to_plain_bullets(text: str, max_lines: int = 30) -> str:
    """Convert arbitrary markdown-ish text to plain '-' bullets and strip markdown artifacts."""
    if not isinstance(text, str):
        return ""
    lines: list[str] = []
    in_code_block = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        stripped = line.strip()
        if not stripped:
            continue
        # Drop markdown headers and emphasis
        stripped = re.sub(r"^#{1,6}\s*", "", stripped)
        stripped = stripped.replace("**", "").replace("__", "").replace("_", "")
        # Normalize bullets/numbered lists
        if re.match(r"^\d+[\.\)]\s+", stripped):
            stripped = re.sub(r"^\d+[\.\)]\s+", "- ", stripped)
        elif stripped.startswith(("* ", "• ", "– ", "— ")):
            stripped = "- " + stripped[2:].lstrip()
        elif stripped.startswith("- "):
            # already ok
            pass
        else:
            # Make non-bullet lines bullets for uniformity
            stripped = "- " + stripped
        lines.append(stripped)
        if len(lines) >= max_lines:
            break
    if not lines:
        return ""
    return "\n".join(lines)

def _extract_top_hunks(diff_chunk: str, max_hunks: int = 2, max_lines_per_hunk: int = 60) -> str:
    """Return up to `max_hunks` hunks from a unified diff chunk, each truncated to `max_lines_per_hunk` lines.
    Keeps headers and context to remain readable while minimizing tokens.
    """
    if not diff_chunk:
        return ""
    lines = diff_chunk.splitlines()
    hunks: list[list[str]] = []
    current: list[str] = []
    found_hunk = False
    for line in lines:
        if line.startswith("@@"):
            # Start of a new hunk
            if current:
                hunks.append(current)
                current = []
            current.append(line)
            found_hunk = True
        else:
            if found_hunk:
                current.append(line)
    if current:
        hunks.append(current)
    # If no explicit hunks, fall back to head of the file diff
    if not hunks:
        return _truncate(diff_chunk, max_lines_per_hunk * 80)
    # Take top hunks
    selected: list[str] = []
    for hunk in hunks[:max_hunks]:
        if len(hunk) > max_lines_per_hunk:
            selected.append("\n".join(hunk[:max_lines_per_hunk] + ["…"]))
        else:
            selected.append("\n".join(hunk))
    return "\n".join(selected)

def explain_single_commit(target: Optional[str], provider: str) -> None:
    # Start spinner immediately
    _sp = ui_utils.spinner("explain ", progress=True)
    _sp.__enter__()
    box: str = ""
    try:
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
        # Keep patch smaller to reduce prompt bloat; we will also trim to top hunks
        raw_patch = get_commit_patch(sha, max_bytes=40_000)
        trimmed_patch = _extract_top_hunks(raw_patch, max_hunks=3, max_lines_per_hunk=60)

        files_preview = "\n".join(f"- {f}" for f in files[:50])
        if len(files) > 50:
            files_preview += f"\n… (+{len(files) - 50} more)"

        prompt_parts: List[str] = [
            "You are a senior engineer. Explain this Git commit for a code review summary.",
            "",
            "Output format requirements:",
            "- Plain text only with simple '-' bullets",
            "- No markdown (no bold, headers, tables, code fences)",
            "- Be concise (<=200 words total)",
            "",
            "Please produce bullets for:",
            "- TL;DR",
            "- Key changes",
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
            ]
        )
        prompt = "\n".join(prompt_parts)
        # Ensure prompt stays under budget by dropping the diff if necessary
        if _estimate_tokens(prompt) > MAX_PROMPT_TOKENS:
            prompt = "\n".join(
                [
                    "You are a senior engineer. Explain this Git commit for a code review summary.",
                    "",
                    "Output format requirements:",
                    "- Plain text only with simple '-' bullets",
                    "- No markdown (no bold, headers, tables, code fences)",
                    "- Be concise (<=180 words total)",
                    "",
                    "Please produce bullets for:",
                    "- TL;DR",
                    "- Key changes",
                    "- Potential risks or regressions",
                    "- Tests to add or update",
                    "",
                    "Commit Metadata:",
                    f"- SHA: {sha}",
                    f"- Author: {author}",
                    f"- Date: {date}",
                    f"- Subject: {subject}",
                    *(["- Body:", _truncate_words(body.strip(), 120)] if body.strip() else []),
                    "",
                    "Files Changed:",
                    files_preview or "(none listed)",
                    "",
                    "Stats:",
                    stats or "(no stats)",
                ]
            )

        response = generate_text(prompt, max_tokens=1800, temperature=0.0)
        # Fallback if provider returned no text
        if isinstance(response, str) and response.strip().startswith("⚠️"):
            compact = "\n".join(
                [
                    "Explain this commit succinctly as plain '-' bullets (<=160 words). No markdown.",
                    f"SHA: {sha}",
                    f"Subject: {subject}",
                    "Files:",
                    files_preview or "(none)",
                    "Stats:",
                    stats or "(no stats)",
                ]
            )
            response = generate_text(compact, max_tokens=700, temperature=0.0)
        response = _sanitize_to_plain_bullets(response, max_lines=28)
        # Prepare box (print after stopping spinner)
        box = ui_utils.format_box(
            title="Chacha — Commit Explanation",
            subtitle=f"Provider: {provider}  •  Commit: {sha[:12]}",
            content=response,
        )
    finally:
        _sp.__exit__(None, None, None)
    if box:
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

    # Cumulative diff (trimmed) and per-file chunks
    cumulative_patch = get_cumulative_diff_patch(base_sha, anchor_sha, max_bytes=30_000)
    file_chunks = dict(split_patch_by_file(cumulative_patch))

    def _should_skip_file(path: str) -> bool:
        p = path.lower()
        if not p:
            return True
        # Skip common noisy/generated files
        if any(x in p for x in ["/dist/", "/build/", "/.next/", "/out/"]):
            return True
        if any(p.endswith(ext) for ext in [".lock", ".min.js", ".map", ".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp"]):
            return True
        if any(name in p for name in ["node_modules/", "vendor/", "__snapshots__/"]):
            return True
        if any(p.endswith(name) for name in ["package-lock.json", "yarn.lock", "pnpm-lock.yaml"]):
            return True
        # Prefer code files; deprioritize non-code
        code_exts = (".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rb", ".rs", ".java", ".kt", ".swift", ".c", ".cc", ".cpp", ".h", ".hpp", ".cs")
        if not p.endswith(code_exts):
            return True
        return False

    # Select important files by churn and filter noise
    selected_files: list[tuple[int, int, str]] = []
    for adds, dels, path in ranked:
        if _should_skip_file(path):
            continue
        if path not in file_chunks:
            continue
        selected_files.append((adds, dels, path))
        if len(selected_files) >= 6:
            break

    # Summarize each selected file with a tiny prompt to save tokens (net-new since base)
    per_file_summaries: list[str] = []
    for adds, dels, path in selected_files:
        chunk = file_chunks.get(path, "")
        if not chunk:
            continue
        chunk = _extract_top_hunks(chunk, max_hunks=2, max_lines_per_hunk=48)
        file_prompt = "\n".join(
            [
                f"Summarize changes in {path} as ONE bullet (<=25 words).",
                "Output plain '-' bullet only; no markdown.",
                f"Stats: +{adds}/-{dels}",
                "Diff (trimmed):",
                _truncate(chunk, 1200),
            ]
        )
        file_summary = generate_text(file_prompt, max_tokens=180, temperature=0.2)
        if isinstance(file_summary, str) and file_summary.strip().startswith("⚠️"):
            # Fallback minimal
            file_summary = f"{path}: (+{adds}/-{dels})"
        per_file_summaries.append(f"- {path} (+{adds}/-{dels}): {_truncate_words(_sanitize_to_plain_bullets(file_summary, max_lines=1), 50)}")

    # Ensure the aggregated per-file section is not too long
    if len("\n".join(per_file_summaries)) > 4000:
        per_file_summaries = per_file_summaries[:4] + ["- … (more files truncated)"]

    # Base commit compact summary (HEAD~N)
    base_subject = get_commit_subject(base_sha)
    base_stats = get_commit_stats(base_sha)
    base_patch = get_commit_patch(base_sha, max_bytes=20_000)
    base_chunks = dict(split_patch_by_file(base_patch))
    base_numstat = get_commit_numstat(base_sha)
    base_ranked = sorted(base_numstat, key=lambda r: (r[0] + r[1]), reverse=True)

    base_selected: list[tuple[int, int, str]] = []
    for adds, dels, path in base_ranked:
        if _should_skip_file(path):
            continue
        if path not in base_chunks:
            continue
        base_selected.append((adds, dels, path))
        if len(base_selected) >= 4:
            break

    base_file_summaries: list[str] = []
    for adds, dels, path in base_selected:
        chunk = base_chunks.get(path, "")
        if not chunk:
            continue
        chunk = _extract_top_hunks(chunk, max_hunks=1, max_lines_per_hunk=40)
        base_prompt = "\n".join(
            [
                f"Summarize changes in base commit file {path} as ONE bullet (<=20 words).",
                "Output plain '-' bullet only; no markdown.",
                f"Stats: +{adds}/-{dels}",
                "Diff (trimmed):",
                _truncate(chunk, 800),
            ]
        )
        base_summary = generate_text(base_prompt, max_tokens=140, temperature=0.2)
        if isinstance(base_summary, str) and base_summary.strip().startswith("⚠️"):
            base_summary = f"{path}: (+{adds}/-{dels})"
        base_file_summaries.append(f"- {path} (+{adds}/-{dels}): {_truncate_words(_sanitize_to_plain_bullets(base_summary, max_lines=1), 40)}")

    prompt = "\n".join(
        [
            "You are a senior engineer. Explain these commits as a cohesive change set.",
            "Focus on the overarching goal, evolution across commits, and net outcomes.",
            "",
            "Output format requirements:",
            "- Plain text with simple '-' bullets only",
            "- No markdown (no bold, headers, tables, code fences)",
            "- Be concise (<=280 words total)",
            "",
            f"Commit range: {base_sha[:12]}..{anchor_sha[:12]} (last {count} commits)",
            "",
            "Commits (oldest → newest):",
            subjects_bullets,
            "",
            "Base commit (compressed view):",
            f"- Subject: {base_subject}",
            f"- Stats: {base_stats or '(no stats)'}",
            *(base_file_summaries if base_file_summaries else ["(no base file summaries)"]),
            "",
            "Cumulative shortstat:",
            shortstat or "(none)",
            "",
            "Net-new since base (top files, compressed):",
            *(per_file_summaries if per_file_summaries else top_files_lines),
            "",
            "Please produce:",
            "- TL;DR",
            "- Key changes by theme",
            "- Risks and potential regressions",
            "- Tests to add or update",
        ]
    )
    # Dynamic pruning to respect prompt token budget
    # If too large, drop per-file summaries from the end, then trim subjects.
    if _estimate_tokens(prompt) > MAX_PROMPT_TOKENS:
        pruned_new = list(per_file_summaries)
        while pruned_new and _estimate_tokens(
            "\n".join(
                [
                    "You are a senior engineer. Explain these commits as a cohesive change set (<=500 words).",
                    "Focus on the overarching goal, how changes evolve across the set, and net outcomes.",
                    "",
                    f"Commit range: {base_sha[:12]}..{anchor_sha[:12]} (last {count} commits)",
                    "",
                    "Commits (oldest → newest):",
                    subjects_bullets,
                    "",
                    "Base commit (compressed view):",
                    f"- Subject: {base_subject}",
                    f"- Stats: {base_stats or '(no stats)'}",
                    *(base_file_summaries if base_file_summaries else ["(no base file summaries)"]),
                    "",
                    "Cumulative shortstat:",
                    shortstat or "(none)",
                    "",
                    "Net-new since base (top files, compressed):",
                    *pruned_new,
                    "",
                    "Please produce:",
                    "- TL;DR (1-2 sentences)",
                    "- Key changes by theme (bulleted)",
                    "- Risks and potential regressions",
                    "- Tests to add or update",
                ]
            )
        ) > MAX_PROMPT_TOKENS:
            pruned_new.pop()
        per_file_summaries = pruned_new
        prompt = "\n".join(
            [
                "You are a senior engineer. Explain these commits as a cohesive change set (<=500 words).",
                "Focus on the overarching goal, how changes evolve across the set, and net outcomes.",
                "",
                f"Commit range: {base_sha[:12]}..{anchor_sha[:12]} (last {count} commits)",
                "",
                "Commits (oldest → newest):",
                subjects_bullets,
                "",
                "Base commit (compressed view):",
                f"- Subject: {base_subject}",
                f"- Stats: {base_stats or '(no stats)'}",
                *(base_file_summaries if base_file_summaries else ["(no base file summaries)"]),
                "",
                "Cumulative shortstat:",
                shortstat or "(none)",
                "",
                "Net-new since base (top files, compressed):",
                *(per_file_summaries if per_file_summaries else top_files_lines),
                "",
                "Please produce:",
                "- TL;DR (1-2 sentences)",
                "- Key changes by theme (bulleted)",
                "- Risks and potential regressions",
                "- Tests to add or update",
            ]
        )
    if _estimate_tokens(prompt) > MAX_PROMPT_TOKENS:
        # Trim subjects to first K lines
        subject_lines = subjects_bullets.splitlines()
        keep = min(8, len(subject_lines))
        subjects_bullets = "\n".join(subject_lines[:keep] + (["…"] if len(subject_lines) > keep else []))
        prompt = "\n".join(
            [
                "You are a senior engineer. Explain these commits as a cohesive change set (<=500 words).",
                "Focus on the overarching goal, how changes evolve across the set, and net outcomes.",
                "",
                f"Commit range: {base_sha[:12]}..{anchor_sha[:12]} (last {count} commits)",
                "",
                "Commits (oldest → newest):",
                subjects_bullets,
                "",
                "Base commit (compressed view):",
                f"- Subject: {base_subject}",
                f"- Stats: {base_stats or '(no stats)'}",
                *(base_file_summaries if base_file_summaries else ["(no base file summaries)"]),
                "",
                "Cumulative shortstat:",
                shortstat or "(none)",
                "",
                "Net-new since base (top files, compressed):",
                *(per_file_summaries if per_file_summaries else top_files_lines),
                "",
                "Please produce:",
                "- TL;DR (1-2 sentences)",
                "- Key changes by theme (bulleted)",
                "- Risks and potential regressions",
                "- Tests to add or update",
            ]
        )
    # Start spinner early for cohesive flow
    _sp2 = ui_utils.spinner("explain ", progress=True)
    _sp2.__enter__()
    box: str = ""
    try:
        response = generate_text(prompt, max_tokens=1400, temperature=0.0)
        if isinstance(response, str) and response.strip().startswith("⚠️"):
            prompt_no_diff = "\n".join(
                [
                    "Explain this cohesive set briefly as plain '-' bullets (<=220 words). No markdown.",
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
            response = generate_text(prompt_no_diff, max_tokens=800, temperature=0.0)
        if isinstance(response, str) and response.strip().startswith("⚠️"):
            tldr_subjects = "; ".join(subjects[:4]) + ("; …" if len(subjects) > 4 else "")
            lines: List[str] = []
            lines.append(f"TL;DR: {count} commits — {tldr_subjects}")
            lines.append("")
            lines.append("Key changes (top files):")
            lines.extend(top_files_lines)
            lines.append("")
            lines.append("Note: Cohesive LLM summary unavailable; showing top changes instead.")
            response = "\n".join(lines)

        response = _sanitize_to_plain_bullets(response, max_lines=36)
        # Prepend a non-LLM "Changed files" section sourced from git
        if top_files:
            changed_files_header = f"- Changed files (top {len(top_files)}):"
            changed_files_block = "\n".join([changed_files_header, *top_files_lines])
        else:
            changed_files_block = "- Changed files: (none)"
        response = changed_files_block + "\n\n" + response
        # Stop spinner before printing
        box = ui_utils.format_box(
            title="Chacha — Cohesive Commit Explanation",
            subtitle=f"Provider: {provider}  •  Commits: {count} (range {base_sha[:12]}..{anchor_sha[:12]})",
            content=response,
        )
    finally:
        _sp2.__exit__(None, None, None)
    if box:
        typer.echo(box)


