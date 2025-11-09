"""Lightweight terminal UI helpers (ASCII box renderer)."""

from __future__ import annotations

import shutil
import textwrap
from typing import Iterable, Optional
import sys
import threading
import time


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


class _Spinner:
    def __init__(self, message_prefix: str = "explain ", frames: Optional[list[str]] = None, interval: float = 0.1) -> None:
        self.message_prefix = message_prefix
        self.frames = frames or ["-", "\\", "|", "/"]
        self.interval = max(0.05, interval)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _loop(self) -> None:
        i = 0
        while not self._stop_event.is_set():
            frame = self.frames[i % len(self.frames)]
            try:
                sys.stderr.write("\r" + self.message_prefix + frame)
                sys.stderr.flush()
            except Exception:
                pass
            time.sleep(self.interval)
            i += 1

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        try:
            self._stop_event.set()
            if self._thread is not None:
                self._thread.join(timeout=0.5)
        except Exception:
            pass
        finally:
            # Clear the spinner line
            try:
                clear_len = max(0, len(self.message_prefix) + 2)
                sys.stderr.write("\r" + (" " * clear_len) + "\r")
                sys.stderr.flush()
            except Exception:
                pass
            self._thread = None


class spinner:
    """Context manager to show a tiny spinner while work is in progress."""

    def __init__(self, message_prefix: str = "explain ", interval: float = 0.1) -> None:
        self._spinner = _Spinner(message_prefix=message_prefix, interval=interval)

    def __enter__(self):
        self._spinner.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self._spinner.stop()
        # Propagate exceptions, if any
        return False

