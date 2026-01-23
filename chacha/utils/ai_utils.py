"""AI utilities using Anthropic (Claude) and Google Gemini APIs.

Includes simple PDF reading support and provider auto-detection.
"""

from __future__ import annotations

import os
import requests
from dotenv import load_dotenv
from typing import Optional
import sys
from datetime import datetime

from chacha.utils.setup import setup_api_key

try:
    from google import genai
except ImportError:
    genai = None  # type: ignore

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

    # Interactive setup if no provider found
    if sys.stdin.isatty():
        setup_api_key()
        # Retry after setup
        return get_provider()

    raise ValueError(
        "❌ No AI provider configured. Set CHACHA_PROVIDER=anthropic|gemini and provide the corresponding API key."
    )


def get_api_key(provider: str) -> str:
    if provider == PROVIDER_ANTHROPIC:
        key = os.getenv("CLAUDE_API_KEY")
        if not key:
            if sys.stdin.isatty():
                setup_api_key(PROVIDER_ANTHROPIC)
                key = os.getenv("CLAUDE_API_KEY")

            if not key:
                raise ValueError("❌ Missing CLAUDE_API_KEY for Anthropic.")
        return key
    if provider == PROVIDER_GEMINI:
        # Prefer GOOGLE_API_KEY if both are set (matches Google guidance)
        key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not key:
            if sys.stdin.isatty():
                setup_api_key(PROVIDER_GEMINI)
                key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

            if not key:
                raise ValueError(
                    "❌ Missing GEMINI_API_KEY (or GOOGLE_API_KEY) for Gemini."
                )
        return key
    raise ValueError(f"❌ Unknown provider: {provider}")


def _is_debug_enabled() -> bool:
    v = (os.getenv("CHACHA_DEBUG") or "").strip().lower()
    return v in {"1", "true", "yes", "on"}


def _get_debug_file() -> Optional[str]:
    path = (os.getenv("CHACHA_DEBUG_FILE") or "").strip()
    return path or None


def _debug_log(message: str) -> None:
    if not _is_debug_enabled():
        return
    timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    header = f"[CHACHA DEBUG {timestamp}] "
    try:
        target_file = _get_debug_file()
        if target_file:
            with open(target_file, "a", encoding="utf-8") as f:
                f.write(header + message + "\n")
        else:
            sys.stderr.write(header + message + "\n")
            sys.stderr.flush()
    except Exception:
        # Never fail the main flow due to debug logging
        pass


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
    model = os.getenv("CHACHA_GEMINI_MODEL") or "gemini-2.5-flash"
    api_version = os.getenv("CHACHA_GEMINI_API_VERSION") or "v1"
    url = (
        f"https://generativelanguage.googleapis.com/{api_version}/models/"
        f"{model}:generateContent?key={api_key}"
    )
    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": f"Explain this code:\n\n{content}"}]}
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 2000,
        },
    }
    response = requests.post(
        url,
        json=payload,
        headers={
            "Content-Type": "application/json",
        },
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


def generate_text(prompt: str, *, max_tokens: int = 2000, temperature: float = 0.2) -> str:
    """Send an arbitrary prompt to the active provider and return text."""
    provider = get_provider()
    if provider == PROVIDER_ANTHROPIC:
        api_key = get_api_key(PROVIDER_ANTHROPIC)
        model = os.getenv("CHACHA_ANTHROPIC_MODEL") or "claude-3-sonnet-20240229"
        if _is_debug_enabled():
            _debug_log(
                "Anthropic request:"
                f"\n- model={model}"
                f"\n- max_tokens={max_tokens}"
                f"\n- temperature={temperature}"
                f"\n- prompt_len_chars={len(prompt)}"
                f"\n- prompt_preview={prompt[:1000]}"
            )
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
            },
            timeout=60,
        )
        if _is_debug_enabled():
            try:
                _debug_log(f"Anthropic response: status={response.status_code} body_preview={response.text[:1200]}")
            except Exception:
                _debug_log("Anthropic response: <unavailable for debug>")
        data = response.json()
        if isinstance(data, dict) and data.get("content"):
            first = data["content"][0]
            if isinstance(first, dict) and "text" in first:
                return first["text"]
        # Surface status or minimal info
        return "⚠️ No response from Anthropic."

    if provider == PROVIDER_GEMINI:
        api_key = get_api_key(PROVIDER_GEMINI)
        model = os.getenv("CHACHA_GEMINI_MODEL") or "gemini-2.5-flash"
        api_version = os.getenv("CHACHA_GEMINI_API_VERSION") or "v1"
        url = (
            f"https://generativelanguage.googleapis.com/{api_version}/models/"
            f"{model}:generateContent?key={api_key}"
        )
        # Optional safety settings override (default: allow all to avoid spurious blocks on diffs)
        safety_env = (os.getenv("CHACHA_GEMINI_SAFETY") or "off").strip().lower()
        safety_settings = None
        if safety_env in {"off", "none", "disable"}:
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
        if _is_debug_enabled():
            _debug_log(
                "Gemini request:"
                f"\n- url={url.split('?')[0]}"
                f"\n- model={model}"
                f"\n- max_tokens={max_tokens}"
                f"\n- temperature={temperature}"
                f"\n- prompt_len_chars={len(prompt)}"
                f"\n- prompt_preview={prompt[:1000]}"
            )
        base_payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "candidateCount": 1,
            },
        }
        if safety_settings is not None:
            base_payload["safetySettings"] = safety_settings  # type: ignore[assignment]
        payload = base_payload
        response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60,
        )
        if _is_debug_enabled():
            try:
                _debug_log(f"Gemini response: status={response.status_code} body_preview={response.text[:1200]}")
            except Exception:
                _debug_log("Gemini response: <unavailable for debug>")
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
        if isinstance(data, dict):
            # Surface prompt-level feedback blocks early
            if "promptFeedback" in data:
                fb = data.get("promptFeedback") or {}
                block = isinstance(fb, dict) and fb.get("blockReason")
                if block:
                    return f"⚠️ Gemini blocked the request: {block}"
            candidates = data.get("candidates")
            if isinstance(candidates, list) and candidates:
                first = candidates[0]
                if isinstance(first, dict):
                    content_obj = first.get("content")
                    # Robust extraction: handle dict or list content shapes
                    def _extract_texts_from_content(content: object) -> list[str]:
                        texts: list[str] = []
                        try:
                            if isinstance(content, dict):
                                parts = content.get("parts")
                                if isinstance(parts, list):
                                    for part in parts:
                                        if isinstance(part, dict) and "text" in part:
                                            txt = str(part.get("text") or "")
                                            if txt:
                                                texts.append(txt)
                            elif isinstance(content, list):
                                for item in content:
                                    if isinstance(item, dict):
                                        parts = item.get("parts")
                                        if isinstance(parts, list):
                                            for part in parts:
                                                if isinstance(part, dict) and "text" in part:
                                                    txt = str(part.get("text") or "")
                                                    if txt:
                                                        texts.append(txt)
                        except Exception:
                            pass
                        return texts
                    texts = _extract_texts_from_content(content_obj)
                    if texts:
                        return "\n".join(texts)
                    # Fallback: surface finish/safety info if no text
                    finish = first.get("finishReason")
                    safety = first.get("safetyRatings")
                    # If we hit MAX_TOKENS without text, retry once with higher output limit
                    if (finish == "MAX_TOKENS") and (max_tokens < 4096):
                        retry_tokens = min(4096, max(1024, max_tokens * 2))
                        retry_payload = dict(base_payload)
                        retry_payload["generationConfig"] = dict(base_payload["generationConfig"])  # type: ignore[index]
                        retry_payload["generationConfig"]["maxOutputTokens"] = retry_tokens  # type: ignore[index]
                        if safety_settings is not None:
                            retry_payload["safetySettings"] = safety_settings  # type: ignore[assignment]
                        if _is_debug_enabled():
                            _debug_log(f"Gemini retry due to MAX_TOKENS with maxOutputTokens={retry_tokens}")
                        retry_resp = requests.post(
                            url,
                            json=retry_payload,
                            headers={"Content-Type": "application/json"},
                            timeout=60,
                        )
                        try:
                            retry_data = retry_resp.json()
                            if isinstance(retry_data, dict):
                                retry_candidates = retry_data.get("candidates")
                                if isinstance(retry_candidates, list) and retry_candidates:
                                    r_first = retry_candidates[0]
                                    if isinstance(r_first, dict):
                                        r_texts = _extract_texts_from_content(r_first.get("content"))
                                        if r_texts:
                                            return "\n".join(r_texts)
                        except Exception:
                            pass
                    if finish or safety:
                        return f"⚠️ Gemini returned no text. Info: finish={finish}, safety={safety}"
        return "⚠️ No response from Gemini."

    return "⚠️ Unsupported provider."


def generate_commit_message(diff: str, staged_files: list[str] | None = None) -> str:
    """Generate a commit message from git diff using AI. PLEASE ONLY RETURN THE COMMIT MESSAGE, NO EXTRA TEXT OR EXPLANATION.
    
    Args:
        diff: The git diff string
        staged_files: Optional list of staged file names for context
    
    Returns:
        A suggested commit message
    """
    if not diff.strip():
        return "⚠️ No changes found to generate commit message."
    
    provider = get_provider()
    
    # Build context about files changed
    files_context = ""
    if staged_files:
        files_context = f"\nFiles changed: {', '.join(staged_files)}\n"
    
    prompt = f"""Generate a concise, clear git commit message for these changes.

{files_context}
Git diff:
{diff}

Rules:
- Use conventional commit format if appropriate (feat:, fix:, refactor:, etc.)
- Keep it under 72 characters for the subject line
- Be specific about what changed
- Use imperative mood ("Add feature" not "Added feature")
- Only return the commit message, no extra text or explanation"""

    if provider == PROVIDER_ANTHROPIC:
        return _generate_commit_with_anthropic(prompt)
    if provider == PROVIDER_GEMINI:
        return _generate_commit_with_gemini(prompt)
    return "⚠️ Unsupported provider."


def _generate_commit_with_anthropic(prompt: str) -> str:
    """Generate commit message using Anthropic Claude."""
    api_key = get_api_key(PROVIDER_ANTHROPIC)
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "content-type": "application/json",
        },
        json={
            "model": "claude-3-sonnet-20240229",
            "max_tokens": 200,
            "messages": [
                {"role": "user", "content": prompt}
            ],
        },
        timeout=60,
    )
    
    if not response.ok:
        return f"⚠️ API error ({response.status_code}): {response.text[:200]}"
    
    data = response.json()
    if isinstance(data, dict) and data.get("content"):
        first = data["content"][0]
        if isinstance(first, dict) and "text" in first:
            return first["text"].strip()
    return "⚠️ No commit message received from Anthropic."


def _generate_commit_with_gemini(prompt: str) -> str:
    """Generate commit message using Google Gemini."""
    if genai is None:
        return "⚠️ google-genai package not installed. Run: pip install google-genai"
    
    # Ensure API key is set in environment for the SDK
    api_key = get_api_key(PROVIDER_GEMINI)
    # The SDK reads from GEMINI_API_KEY or GOOGLE_API_KEY env var
    if not os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
        os.environ["GEMINI_API_KEY"] = api_key
    
    try:
        # The client gets the API key from the environment variable
        client = genai.Client()
        
        # Get model from env or use default
        model = os.getenv("CHACHA_GEMINI_MODEL") or "gemini-2.0-flash"
        
        response = client.models.generate_content(
            model=model,
            contents=prompt
        )
        
        if response and hasattr(response, 'text') and response.text:
            return response.text.strip()
        
        return "⚠️ No commit message received from Gemini."
    except Exception as e:
        error_msg = str(e)
        if hasattr(e, 'message'):
            error_msg = e.message
        return f"⚠️ Gemini error: {error_msg}"

