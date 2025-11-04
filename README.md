# Chacha CLI

Chacha is a lightweight CLI toolkit providing developer helpers:
- explain: placeholder for code explanations
- fix: placeholder for automated fixes
- explain-commit: placeholder for explaining commits
- commit: placeholder for smart commit workflows

## Installation

```bash
pip install .
```

This will install the `chacha` console command.

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
Send content to Claude API
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

Copy `.env.example` to `.env` and adjust values as needed.

## License

MIT


