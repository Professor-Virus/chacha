# Chacha CLI

Chacha is a productivity-first developer assistant for your terminal. It wraps common Git and AI-assisted workflows behind a single CLI so you can review changes, craft commits, and explain code without leaving your shell.

## Key Features

- **Smart commits** – stage files interactively (Questionary) or all at once, auto-generate a commit message, confirm the branch, and push in one go.
- **Explain code** – send source or PDFs to your configured AI provider and get a concise explanation back.
- **Fix suggestions** – experiment with AI-generated refactors or fixes for a given file.
- **Explain commit history** – summarize the latest commit by feeding the message and diff to the AI.
- **Branch insights (planned)** – Rich-powered dashboard to inspect remote branches, latest commit metadata, and divergence status.

## Installation

### Local development

Use `pipx` to install from your working tree and pick up changes quickly:

```bash
# first install
pipx install .

# reinstall after edits
pipx reinstall .

# if changes fail to appear
pipx uninstall chacha-cli
pipx install .
```

### From GitHub

Install the published CLI straight from the repository:

```bash
# latest main
pipx install --spec git+https://github.com/Professor-Virus/chacha.git@main chacha-cli

# specific branch
pipx install --spec git+https://github.com/Professor-Virus/chacha.git@feature/my-branch chacha-cli

# update
pipx uninstall chacha-cli
pipx install --spec git+https://github.com/Professor-Virus/chacha.git@main chacha-cli
```

> GitHub installs require your changes to be pushed. For local experimentation prefer `pipx install .`.

## Usage Overview

```bash
chacha --help              # global help and options
chacha commit --help       # smart commit workflow
chacha explain PATH        # explain a file or PDF
chacha fix PATH            # request AI-driven improvements
chacha explain-commit      # summarize the latest commit
```

### Smart commit workflow

1. `chacha run commit`  
   - Presents a multi-select list of changed files (Questionary).  
   - Shows a generated commit message, the target branch, and asks for confirmation.  
   - On approval, commits and pushes to the current or specified branch.

2. `chacha run commit --auto`  
   - Stages every changed file without prompting before generating the commit message.

Both flows rely on `git_utils` helpers for staging, diff collection, commit creation, and pushing.

### Explain & fix commands

- `explain` reads the given file, delegates to the configured AI provider, and prints the response with minimal formatting.
- `fix` (experimental) sends the file to the AI with “suggest improvements” prompting. Apply suggestions manually for now.
- `explain-commit` grabs the latest commit diff/message and asks the AI to narrate the change.

## Configuration

Chacha detects which AI provider to use based on environment variables:

- Explicit selection  
  - `CHACHA_PROVIDER=anthropic` with `CLAUDE_API_KEY`
  - `CHACHA_PROVIDER=gemini` with `GEMINI_API_KEY` (or `GOOGLE_API_KEY`)
- Auto-detection (no `CHACHA_PROVIDER`)  
  - `CLAUDE_API_KEY` present → uses Anthropic  
  - Otherwise falls back to Gemini if `GEMINI_API_KEY` or `GOOGLE_API_KEY` is present

Examples:

```bash
# Anthropic (Claude)
export CHACHA_PROVIDER=anthropic
export CLAUDE_API_KEY=sk-ant-...

# Google Gemini
export CHACHA_PROVIDER=gemini
export GEMINI_API_KEY=AIza...
```

The CLI requires Python 3.9+ and keeps third-party dependencies minimal.

## Roadmap Ideas

- Rich-based branch monitor with live status and interactive checkouts (using Questionary prompts for actions).
- AI-assisted “apply fix” flow that writes changes directly to files.
- Template-driven commit messages for conventional commits.

## License

MIT