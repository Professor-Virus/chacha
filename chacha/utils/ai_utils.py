"""AI utilities using Anthropic (Claude) and Google Gemini APIs.

Includes simple PDF reading support and provider auto-detection.
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

PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_GEMINI = "gemini"


def _normalize_provider(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    v = value.strip().lower()
    if v in {PROVIDER_ANTHROPIC, PROVIDER_GEMINI}:
        return v
    return None


def get_provider() -> str:
    """Return the active provider.

    Resolution order:
    1) CHACHA_PROVIDER if valid ("anthropic" or "gemini")
    2) Auto-detect by env keys (CLAUDE_API_KEY -> anthropic, GEMINI_API_KEY/GOOGLE_API_KEY -> gemini)
    3) Error if none found
    """
    configured = _normalize_provider(os.getenv("CHACHA_PROVIDER"))
    if configured:
        return configured

    if os.getenv("CLAUDE_API_KEY"):
        return PROVIDER_ANTHROPIC
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        return PROVIDER_GEMINI

    raise ValueError(
        "❌ No AI provider configured. Set CHACHA_PROVIDER=anthropic|gemini and provide the corresponding API key."
    )


def get_api_key(provider: str) -> str:
    if provider == PROVIDER_ANTHROPIC:
        key = os.getenv("CLAUDE_API_KEY")
        if not key:
            raise ValueError("❌ Missing CLAUDE_API_KEY for Anthropic.")
        return key
    if provider == PROVIDER_GEMINI:
        key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise ValueError(
                "❌ Missing GEMINI_API_KEY (or GOOGLE_API_KEY) for Gemini."
            )
        return key
    raise ValueError(f"❌ Unknown provider: {provider}")


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
    provider = get_provider()
    content = _read_file_content(path)
    if provider == PROVIDER_ANTHROPIC:
        return _explain_with_anthropic(content)
    if provider == PROVIDER_GEMINI:
        return _explain_with_gemini(content)
    return "⚠️ Unsupported provider."


def _explain_with_anthropic(content: str) -> str:
    api_key = get_api_key(PROVIDER_ANTHROPIC)
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
    if isinstance(data, dict) and data.get("content"):
        first = data["content"][0]
        if isinstance(first, dict) and "text" in first:
            return first["text"]
    return "⚠️ No explanation received from Anthropic."


def _explain_with_gemini(content: str) -> str:
    api_key = get_api_key(PROVIDER_GEMINI)
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.5-flash"
        f"?key={api_key}"
    )
    payload = {
        "contents": [
            {"parts": [{"text": f"Explain this code:\n\n{content}"}]}
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 2000,
        },
    }
    response = requests.post(
        url,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=60,
    )

    # Non-200 → surface server error message
    if response.status_code != 200:
        try:
            err = response.json()
            if isinstance(err, dict) and "error" in err:
                msg = err.get("error", {}).get("message") or str(err)
                return f"⚠️ Gemini error ({response.status_code}): {msg}"
            return f"⚠️ Gemini HTTP {response.status_code}: {response.text[:500]}"
        except Exception:
            return f"⚠️ Gemini HTTP {response.status_code}: {response.text[:500]}"

    data = response.json()

    # API-level error envelope
    if isinstance(data, dict) and "error" in data:
        msg = data.get("error", {}).get("message") or str(data)
        return f"⚠️ Gemini error: {msg}"

    # Safety/prompt feedback
    if isinstance(data, dict) and "promptFeedback" in data:
        fb = data.get("promptFeedback") or {}
        block = fb.get("blockReason")
        if block:
            return f"⚠️ Gemini blocked the request: {block}"

    # Normal candidate extraction
    if isinstance(data, dict):
        candidates = data.get("candidates")
        if isinstance(candidates, list) and candidates:
            first = candidates[0]
            # If there's text, return it, otherwise surface finish reason
            if isinstance(first, dict):
                content_obj = first.get("content")
                if isinstance(content_obj, dict):
                    parts = content_obj.get("parts")
                    if isinstance(parts, list) and parts:
                        part0 = parts[0]
                        if isinstance(part0, dict) and "text" in part0:
                            return str(part0["text"]) or ""
                finish = first.get("finishReason") or first.get("safetyRatings")
                if finish:
                    return f"⚠️ Gemini returned no text. Info: {finish}"

    return "⚠️ No explanation received from Gemini."


