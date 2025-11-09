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
    
    # Separate files by status
    staged = [f for f, status in all_files.items() if status in ["staged", "both"]]
    unstaged = [f for f, status in all_files.items() if status in ["unstaged", "both"]]
    
    # Build choices for questionary
    choices = []
    
    # Add staged files (marked as checked)
    for filename in staged:
        if filename in unstaged:
            # File has both staged and unstaged changes
            choices.append(
                questionary.Choice(
                    title=f"✓ {filename} (staged + unstaged)",
                    value=filename,
                    checked=True,
                )
            )
        else:
            # File is fully staged
            choices.append(
                questionary.Choice(
                    title=f"✓ {filename} (staged)",
                    value=filename,
                    checked=True,
                )
            )
    
    # Add unstaged files (not checked)
    for filename in unstaged:
        if filename not in staged:
            choices.append(
                questionary.Choice(
                    title=f"  {filename} (unstaged)",
                    value=filename,
                    checked=False,
                )
            )
    
    # Show interactive file selection
    typer.echo("\n📋 Select files to stage for commit:\n")
    selected_files = questionary.checkbox(
        "Choose files (Space to select, Enter to confirm):",
        choices=choices,
    ).ask()
    
    if selected_files is None:
        typer.echo("❌ Cancelled.")
        raise typer.Exit(1)
    
    if not selected_files:
        typer.echo("❌ No files selected.")
        raise typer.Exit(1)
    
    # Stage the selected files
    typer.echo(f"\n📦 Staging {len(selected_files)} file(s)...")
    success, error_msg = stage_files(selected_files)
    if not success:
        typer.echo(f"❌ Failed to stage files: {error_msg}")
        raise typer.Exit(1)
    
    typer.echo("✅ Files staged successfully!\n")
    
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
    
