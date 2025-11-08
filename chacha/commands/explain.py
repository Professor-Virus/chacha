"""Explain command using Typer."""

from __future__ import annotations

import typer

from chacha.utils.ai_utils import explain_file
from . import explain_commit


app = typer.Typer()

app.add_typer(explain_commit.app, name="commit")


@app.command()
def file(path: str) -> None:
    """Explain a file (code or PDF) using Claude."""
    typer.echo(f"🧠 Explaining {path}...")
    explanation = explain_file(path)
    typer.echo(explanation)


