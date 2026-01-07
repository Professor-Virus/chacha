# Chacha CLI

Chacha is a productivity-first developer assistant for your terminal. It wraps common Git and AI-assisted workflows behind a single CLI so you can review changes, craft commits, and explain code without leaving your shell.

## Key Features

- **Smart commits** – stage files interactively (Questionary) or all at once, auto-generate a commit message, confirm the branch, and push in one go.
- **Explain code** – send source or PDFs to your configured AI provider and get a concise explanation back.
- **Fix suggestions** – experiment with AI-generated refactors or fixes for a given file.
- **Explain commit history** – summarize the latest commit by feeding the message and diff to the AI.
- **Branch insights (planned)** – Rich-powered dashboard to inspect remote branches, latest commit metadata, and divergence status.

## Installation

### Getting Started 🚀

Install the published CLI straight from the repository:

```bash
# Install latest main
pipx install --spec git+https://github.com/Professor-Virus/chacha.git@main chacha-cli

# Uninstall
pipx uninstall chacha-cli

```

### Smart commit workflow

1. `chacha commit run`  
   - Presents a multi-select list of changed files (Questionary).  
   - Shows a generated commit message, the target branch, and asks for confirmation.  
   - On approval, commits and pushes to the current or specified branch.

2. `chacha commit run --auto`  
   - Stages every changed file without prompting before generating the commit message.


### Explain commit workflow

1.  `chacha explain commit [TARGET] or --spec`
      --> TARGET is a commit hash
      --> --spec will expain the last commit

2. `chacha explain commit -c N`
      --> Explains the past N commits

### Last Step


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