"""Chacha CLI tool"""

from __future__ import annotations

import typer

from chacha.commands import fix, explain, commit, setup


app = typer.Typer(help="🕺 Chacha — your AI-powered CLI for explaining and committing code")

# Register subcommands
app.add_typer(fix.app, name="fix")
app.add_typer(explain.app, name="explain")
app.add_typer(commit.app, name="commit")
app.add_typer(setup.app, name="setup")


if __name__ == "__main__":  # pragma: no cover
    app()


