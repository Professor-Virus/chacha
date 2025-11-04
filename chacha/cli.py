"""Chacha CLI entrypoint (Typer-based)."""

from __future__ import annotations

import typer

from chacha.commands import explain, fix, explain_commit, commit


app = typer.Typer(help="🕺 Chacha — your AI-powered CLI for explaining and committing code")

# Register subcommands
app.add_typer(explain.app, name="explain")
app.add_typer(fix.app, name="fix")
app.add_typer(explain_commit.app, name="explain-commit")
app.add_typer(commit.app, name="commit")


if __name__ == "__main__":  # pragma: no cover
    app()


