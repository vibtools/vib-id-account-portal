#!/usr/bin/env python3
"""Reject release blockers, placeholders, and forbidden sensitive artifacts."""

from __future__ import annotations

import re
from pathlib import Path

TEXT_SUFFIXES = {".py", ".html", ".css", ".js", ".md", ".toml", ".yaml", ".yml", ".ini", ".sh"}
FORBIDDEN_PATTERNS = {
    "TODO marker": re.compile(r"\bTODO\b", re.IGNORECASE),
    "FIXME marker": re.compile(r"\bFIXME\b", re.IGNORECASE),
    "placeholder implementation": re.compile(r"notimplementederror|implement later", re.IGNORECASE),
    "browser token storage": re.compile(
        r"(?:localStorage|sessionStorage).*(?:token|secret)", re.IGNORECASE
    ),
    "password grant": re.compile(r"grant_type[\"']?\s*[:=]\s*[\"']password", re.IGNORECASE),
}
IGNORED_DIRS = {".venv", ".git", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


def main() -> None:
    root = Path.cwd()
    failures: list[str] = []
    if Path(".env").exists():
        failures.append(".env must not be included in a release")
    for path in root.rglob("*"):
        if not path.is_file() or any(part in IGNORED_DIRS for part in path.parts):
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for label, pattern in FORBIDDEN_PATTERNS.items():
            if pattern.search(text):
                failures.append(f"{path}: {label}")
    if failures:
        raise SystemExit("\n".join(failures))
    print("Release integrity checks passed")


if __name__ == "__main__":
    main()
