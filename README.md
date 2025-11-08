# Chacha CLI

Chacha is a lightweight CLI toolkit providing developer helpers:
- explain: placeholder for code explanations
- fix: placeholder for automated fixes
- explain-commit: placeholder for explaining commits
- commit: placeholder for smart commit workflows

## Installation

### For Local Development (Recommended)

If you're developing locally and want to test changes immediately:

```bash
# First time
pipx install .

# After making changes, reinstall
pipx reinstall .
```

This installs from your local directory and picks up your changes immediately.

### From GitHub (Production/Shared)

To install from the GitHub repository:

```bash
# Install from main branch
pipx install --spec git+https://github.com/Professor-Virus/chacha.git@main chacha-cli

# Install from a specific branch
pipx install --spec git+https://github.com/Professor-Virus/chacha.git@branch-name chacha-cli

# To reinstall/update from GitHub
pipx uninstall chacha-cli
pipx install --spec git+https://github.com/Professor-Virus/chacha.git@branch-name chacha-cli
```

**Note:** Installing from GitHub requires you to push your changes first. For local development, use `pipx install .` instead.

## Usage

```bash
chacha --help
chacha explain --help
chacha fix --help
chacha explain-commit --help
chacha commit --help
```

## Development


1. explain
Input: file path (Python, JS, PDF)
Flow:
Read file content
If PDF → extract text (PyPDF2)
Send content to configured AI provider (Anthropic Claude or Google Gemini)
Print result in formatted output
File: commands/explain.py
Depends on: utils/ai_utils.py and utils/file_utils.py

2. fix
Input: file path
Flow:
Read code
Send to Claude with “Suggest fixes/improvements” prompt
Display diff-like output (optional)
Later: add “apply fix” option (rewrite file)

3. explain-commit
Flow:
Use GitPython to get last commit message and diff
Send both to Claude
Display summary or “story of the commit”



- Python >= 3.9
- No required third-party dependencies by default

## Environment

Set one of the supported providers and its API key. You can export these in your shell profile or place them in a `.env` file in the directory where you run the command.

Provider selection (any one of these works):

- Explicitly choose a provider:
  - `CHACHA_PROVIDER=anthropic` with `CLAUDE_API_KEY=...`
  - `CHACHA_PROVIDER=gemini` with `GEMINI_API_KEY=...` (or `GOOGLE_API_KEY=...`)

- Auto-detection (no `CHACHA_PROVIDER`):
  - If `CLAUDE_API_KEY` is set → uses Anthropic
  - Else if `GEMINI_API_KEY` or `GOOGLE_API_KEY` is set → uses Gemini

Examples:

```bash
# Anthropic (Claude)
export CHACHA_PROVIDER=anthropic
export CLAUDE_API_KEY=sk-ant-...

# Google Gemini
export CHACHA_PROVIDER=gemini
export GEMINI_API_KEY=AIza...
```

## License

MIT