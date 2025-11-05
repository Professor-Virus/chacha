"""Chacha CLI entrypoint (Typer-based)."""

from __future__ import annotations

import typer

from chacha.commands import fix, explain_commit, commit
from chacha.utils.ai_utils import explain_file


app = typer.Typer(help="🕺 Chacha — your AI-powered CLI for explaining and committing code")

# Direct command: `chacha explain <path>`
@app.command()
def explain(path: str) -> None:
    """Explain a file (code or PDF) using Claude."""
    typer.echo(f"🧠 Explaining {path}...")
    explanation = explain_file(path)
    typer.echo(explanation)

# Register remaining subcommands
app.add_typer(fix.app, name="fix")
app.add_typer(explain_commit.app, name="explain-commit")
app.add_typer(commit.app, name="commit")


if __name__ == "__main__":  # pragma: no cover
    app()


