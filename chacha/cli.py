"""Chacha CLI entrypoint (Typer-based)."""

from __future__ import annotations

import typer

from chacha.commands import fix, explain_commit, commit
from chacha.utils.ai_utils import explain_file, get_provider
from chacha.utils.ui_utils import format_box


app = typer.Typer(help="🕺 Chacha — your AI-powered CLI for explaining and committing code")

# Direct command: `chacha explain <path>`
@app.command()
def explain(path: str) -> None:
    """Explain a file (code or PDF) with a nicely formatted output."""
    typer.echo(f"🧠 Explaining {path}...")
    explanation = explain_file(path)
    try:
        provider = get_provider()
    except Exception:
        provider = "unknown"
    box = format_box(
        title="Chacha — Explanation",
        subtitle=f"File: {path}  •  Provider: {provider}",
        content=explanation,
    )
    typer.echo(box)

# Register remaining subcommands
app.add_typer(fix.app, name="fix")
app.add_typer(explain_commit.app, name="explain-commit")
app.add_typer(commit.app, name="commit")


if __name__ == "__main__":  # pragma: no cover
    app()


