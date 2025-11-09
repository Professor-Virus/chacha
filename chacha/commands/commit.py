"""Commit command using Typer."""

from __future__ import annotations

import typer
import questionary

from chacha.utils.ai_utils import generate_commit_message
from chacha.utils.git_utils import (
    get_staged_diff,
    get_staged_files,
    get_all_changes_diff,
    stage_files,
    get_changed_files,
    commit_and_push,
    get_upstream_branch,
)


app = typer.Typer()


@app.command()
def run(
    auto: bool = typer.Option(False, "--auto", "-a", help="Automatically commit with generated message"),
) -> None:
    """Generate a smart commit message from staged changes."""
    # Get all changed files with their status
    all_files = get_changed_files()
    
    if not all_files:
        typer.echo("❌ No changed files found. Nothing to commit.")
        raise typer.Exit(1)
    
    
    if auto:
        files_to_stage = all_files
    else:
        files_to_stage = questionary.checkbox(
            "Select files to stage",
            choices=all_files,
        ).ask()
        if not files_to_stage:
            typer.echo("❌ No files selected. Nothing to stage.")
            raise typer.Exit(1)

    success, error = stage_files(files_to_stage)
    if not success:
        typer.echo(f"❌ Failed to stage files: {error}")
        raise typer.Exit(1)

    typer.echo("✅ Files staged successfully!\n")
    
    # Get the diff of staged files
    diff = get_staged_diff()
    
    if not diff.strip():
        typer.echo("⚠️ No diff available for staged files.")
        raise typer.Exit(1)
    
    typer.echo(f"📝 Files to commit: {', '.join(all_files)}")
    typer.echo("🤖 Generating commit message...\n")
    
    # Generate commit message
    commit_message = generate_commit_message(diff, all_files)
    
    branch_name = get_upstream_branch()
    if not branch_name:
        branch_name = questionary.text("No upstream branch found. Enter branch name to push to:", default="").ask()
        if branch_name:
            branch_name = branch_name.strip()

    typer.echo("💡 Suggested commit message:")
    typer.echo("─" * 60)
    typer.echo(commit_message)
    typer.echo("─" * 60)
    typer.echo(f"🌿 Target branch: {branch_name or 'N/A'}\n")

    confirm = questionary.confirm("Proceed with this commit?", default=True).ask()
    if not confirm:
        typer.echo("🚫 Commit cancelled.")
        raise typer.Exit(0)

    if not branch_name:
        typer.echo("❌ No branch specified. Cannot commit.")
        raise typer.Exit(1)

    success, error = commit_and_push(branch_name, commit_message)
    if not success:
        typer.echo(f"❌ Commit failed: {error}")
        raise typer.Exit(1)

    typer.echo("✅ Commit created and pushed successfully!")

