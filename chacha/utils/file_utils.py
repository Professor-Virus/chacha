"""File utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable


def read_text(path: str | Path, default: str = "") -> str:
    p = Path(path)
    if not p.exists():
        return default
    return p.read_text(encoding="utf-8")


def write_text(path: str | Path, content: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def list_files(root: str | Path, patterns: Iterable[str] | None = None) -> list[Path]:
    p = Path(root)
    if not p.exists():
        return []
    if not patterns:
        return [f for f in p.rglob("*") if f.is_file()]

    result: list[Path] = []
    for pattern in patterns:
        result.extend([f for f in p.rglob(pattern) if f.is_file()])
    # Deduplicate
    seen: set[Path] = set()
    unique: list[Path] = []
    for f in result:
        if f not in seen:
            seen.add(f)
            unique.append(f)
    return unique


