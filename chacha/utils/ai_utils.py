"""AI utilities using Claude via Anthropic API.

Includes simple PDF reading support.
"""

from __future__ import annotations

import os
import requests
from dotenv import load_dotenv
from typing import Optional

try:
    from PyPDF2 import PdfReader  # type: ignore
except Exception:  # pragma: no cover - optional at runtime
    PdfReader = None  # type: ignore


load_dotenv()


def get_api_key() -> str:
    key = os.getenv("CLAUDE_API_KEY")
    if not key:
        raise ValueError(
            "❌ Missing CLAUDE_API_KEY. Please set it in your .env or environment."
        )
    return key


def _read_file_content(path: str) -> str:
    lower = path.lower()
    if lower.endswith(".pdf") and PdfReader is not None:
        try:
            reader = PdfReader(path)
            text_parts: list[str] = []
            for page in reader.pages:
                text_parts.append(page.extract_text() or "")
            return "\n".join(text_parts).strip()
        except Exception:
            # Fall back to raw bytes decode if PDF parsing fails
            pass
    # Default: read as text
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def explain_file(path: str) -> str:
    api_key = get_api_key()
    content = _read_file_content(path)

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "content-type": "application/json",
        },
        json={
            "model": "claude-3-sonnet-20240229",
            "max_tokens": 2000,
            "messages": [
                {"role": "user", "content": f"Explain this code:\n\n{content}"}
            ],
        },
        timeout=60,
    )

    data = response.json()
    if isinstance(data, dict) and "content" in data and data["content"]:
        first = data["content"][0]
        if isinstance(first, dict) and "text" in first:
            return first["text"]
    return "⚠️ No explanation received."


