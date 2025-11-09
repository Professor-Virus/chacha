"""Commit command using Typer."""

from __future__ import annotations

import typer
import questionary

from chacha.utils.ai_utils import generate_commit_message
from chacha.utils.git_utils import (
    get_staged_diff,
    get_staged_files,
    get_all_changes_diff,
    get_all_changed_files,
    stage_files,
)


app = typer.Typer()


@app.command()
def run(
    auto: bool = typer.Option(False, "--auto", "-a", help="Automatically commit with generated message"),
) -> None:
    """Generate a smart commit message from staged changes."""
    # Get all changed files with their status
    all_files = get_all_changed_files()
    
    if not all_files:
        typer.echo("❌ No changed files found. Nothing to commit.")
        raise typer.Exit(1)
    
    
    stage_files()

    typer.echo("✅ Files staged successfully!\n")
    typer.echo(all_files)
    
    # Get the diff of staged files
    diff = get_staged_diff()
    
    if not diff.strip():
        typer.echo("⚠️ No diff available for staged files.")
        raise typer.Exit(1)
    
    typer.echo(f"📝 Files to commit: {', '.join(selected_files)}")
    typer.echo("🤖 Generating commit message...\n")
    
    # Generate commit message
    commit_message = generate_commit_message(diff, selected_files)
    
    typer.echo("💡 Suggested commit message:")
    typer.echo("─" * 60)
    typer.echo(commit_message)
    typer.echo("─" * 60)
    
