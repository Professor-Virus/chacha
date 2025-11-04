"""Config helpers.

Loads `.env` if `python-dotenv` is installed; otherwise uses OS env only.
"""

from __future__ import annotations

import os
from typing import Optional


def _try_load_dotenv() -> None:
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv()
    except Exception:
        # Optional dependency; fail silently if not present.
        pass


_try_load_dotenv()


def get_env(key: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(key, default)


