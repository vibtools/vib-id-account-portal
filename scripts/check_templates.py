#!/usr/bin/env python3
"""Parse every Jinja template and reject unsafe template constructs."""

from __future__ import annotations

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

FORBIDDEN = ("|safe", "localStorage", "sessionStorage", "javascript:")
INLINE_EVENT = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)


def main() -> None:
    root = Path("app/templates")
    environment = Environment(loader=FileSystemLoader(str(root)), autoescape=True)
    failures: list[str] = []
    for path in sorted(root.rglob("*.html")):
        relative = path.relative_to(root).as_posix()
        source = path.read_text(encoding="utf-8")
        try:
            environment.parse(source)
        except Exception as exc:
            failures.append(f"{relative}: parse error: {exc}")
        for token in FORBIDDEN:
            if token in source:
                failures.append(f"{relative}: forbidden token {token}")
        if INLINE_EVENT.search(source):
            failures.append(f"{relative}: inline event handler conflicts with CSP")
    if failures:
        raise SystemExit("\n".join(failures))
    print(f"Parsed {len(list(root.rglob('*.html')))} templates successfully")


if __name__ == "__main__":
    main()
