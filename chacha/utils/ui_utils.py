"""Lightweight terminal UI helpers (ASCII box renderer)."""

from __future__ import annotations

import shutil
import textwrap
from typing import Iterable, Optional


def _get_terminal_width(default: int = 100) -> int:
    try:
        columns = shutil.get_terminal_size().columns
        return max(40, min(columns, 140))  # sensible bounds
    except Exception:
        return default


def _wrap_content_lines(content: str, max_width: int) -> list[str]:
    wrapped: list[str] = []
    in_code_block = False
    for line in content.splitlines() or [""]:
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            wrapped.append(line)
            continue
        if in_code_block or len(line) <= max_width:
            wrapped.append(line)
        else:
            wrapped.extend(textwrap.wrap(line, width=max_width, replace_whitespace=False))
    if not wrapped:
        wrapped.append("")
    return wrapped


def format_box(title: str, content: str, subtitle: Optional[str] = None, width: Optional[int] = None) -> str:
    """Return a string containing a nicely formatted ASCII box.

    - title: shown in the top border
    - subtitle: optional line below the top border
    - content: main body, wrapped to width
    - width: optional overall box width; defaults to terminal width
    """
    box_width = width or _get_terminal_width()
    inner_width = max(20, box_width - 2)  # account for side borders

    # Top border with centered title
    clean_title = (title or "").strip()
    title_segment = f" {clean_title} " if clean_title else ""
    # Use unicode box-drawing for nicer look; pure ASCII fallback if needed by future callers
    top_border = "┌" + title_segment.center(inner_width, "─") + "┐"

    lines: list[str] = [top_border]

    if subtitle:
        sub = subtitle.strip()
        for seg in _wrap_content_lines(sub, inner_width - 2):
            lines.append("│ " + seg.ljust(inner_width - 2) + " │")
        lines.append("├" + ("─" * inner_width) + "┤")
    else:
        lines.append("├" + ("─" * inner_width) + "┤")

    for seg in _wrap_content_lines(content, inner_width - 2):
        lines.append("│ " + seg.ljust(inner_width - 2) + " │")

    lines.append("└" + ("─" * inner_width) + "┘")
    return "\n".join(lines)


