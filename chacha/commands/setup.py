import os
import typer
import questionary

app = typer.Typer()


def detect_shell() -> str:
    """Detect the user's shell (zsh or bash)."""
    shell = os.environ.get("SHELL", "")
    if "zsh" in shell.lower():
        return "zsh"
    elif "bash" in shell.lower():
        return "bash"
    else:
        # Default to zsh if can't detect
        return "zsh"


@app.command()
def run() -> None:
    """Setup the CLI."""
    typer.echo("🔧 Pick your AI provider")
    provider = questionary.select(
        "Select your AI provider",
        choices=["Anthropic", "Gemini"],
    ).ask()
    
    if not provider:
        typer.echo("❌ No provider selected. Exiting.")
        return
    
    # Detect shell
    shell = detect_shell()
    rc_file = f".{shell}rc"
    rc_path = os.path.expanduser(f"~/{rc_file}")
    
    # Determine environment variable name
    if provider == "Anthropic":
        env_var = "CLAUDE_API_KEY"
    elif provider == "Gemini":
        env_var = "GEMINI_API_KEY"
    else:
        typer.echo(f"❌ Unknown provider: {provider}")
        return
    
    # Ask if user wants to edit rc file
    edit_rc = questionary.confirm(
        f"Do you want us to edit your ~/{rc_file}?",
        default=True
    ).ask()
    
    if edit_rc:
        # Ask for API key
        api_key = questionary.password(f"Enter your {env_var}:").ask()
        
        if not api_key:
            typer.echo("❌ No API key provided. Exiting.")
            return
        
        # Append to rc file
        export_line = f"export {env_var}={api_key}\n"
        
        # Check if the line already exists
        lines = []
        if os.path.exists(rc_path):
            with open(rc_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        
        # Remove existing line for this env var if it exists
        lines = [line for line in lines if not line.strip().startswith(f"export {env_var}=")]
        
        # Ensure file ends with newline
        if lines and not lines[-1].endswith("\n"):
            lines.append("\n")
        
        # Append new export line
        lines.append(export_line)
        
        # Write back to file
        with open(rc_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        
        typer.echo(f"✅ Added {env_var} to {rc_path}")
        typer.echo(f"💡 Run 'source ~/{rc_file}' or restart your terminal to apply changes.")
        typer.echo(f"🧪 Test by running 'echo $" + env_var + "'")

    else:
        # Print instructions
        typer.echo(f"\n📝 To set {env_var} manually, run:")
        typer.echo(f"   echo 'export {env_var}=your_api_key_here' >> ~/{rc_file}")
        typer.echo(f"\n💡 Then run 'source ~/{rc_file}' or restart your terminal.")
    