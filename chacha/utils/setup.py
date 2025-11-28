"""Interactive setup for API keys."""

from __future__ import annotations

import os
import sys
import typer
from dotenv import load_dotenv

from chacha.utils.ui_utils import format_box

PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_GEMINI = "gemini"


def setup_api_key(provider: str | None = None) -> None:
    """Interactive setup for API keys."""

    if not provider:
        # Ask user to choose provider
        box_content = (
            "No AI provider configured.\n\n"
            "Please select a provider to set up:\n"
            "1. Anthropic (Claude)\n"
            "2. Google Gemini"
        )
        print(format_box("Chacha Setup", box_content))

        choice = typer.prompt("Select option", type=int, default=1)
        if choice == 1:
            provider = PROVIDER_ANTHROPIC
        elif choice == 2:
            provider = PROVIDER_GEMINI
        else:
            typer.echo("Invalid choice. Defaulting to Anthropic.")
            provider = PROVIDER_ANTHROPIC

    # Prompt for key
    if provider == PROVIDER_ANTHROPIC:
        env_var = "CLAUDE_API_KEY"
        name = "Anthropic (Claude)"
        url = "https://console.anthropic.com/"
    elif provider == PROVIDER_GEMINI:
        env_var = "GEMINI_API_KEY"
        name = "Google Gemini"
        url = "https://aistudio.google.com/"
    else:
        typer.echo(f"Unknown provider: {provider}")
        return

    box_content = (
        f"Please enter your API key for {name}.\n"
        f"It will be saved to .env in the current directory.\n\n"
        f"Get your key at:\n{url}"
    )
    print(format_box(f"Setup {name}", box_content))

    api_key = typer.prompt(f"Enter {env_var}", hide_input=True)

    if not api_key:
        typer.echo("No key entered. Aborting setup.")
        sys.exit(1)

    # Save to .env
    env_path = os.path.join(os.getcwd(), ".env")

    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    # Remove existing key for this var to replace it
    lines = [line for line in lines if not line.strip().startswith(f"{env_var}=")]

    if lines and not lines[-1].endswith("\n"):
        lines.append("\n")

    lines.append(f"{env_var}={api_key}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    typer.echo(f"✅ Saved {env_var} to {env_path}")

    # Reload env
    load_dotenv(override=True)
