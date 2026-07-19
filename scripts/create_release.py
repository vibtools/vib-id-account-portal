#!/usr/bin/env python3
"""Create a deterministic source release archive and SHA-256 checksum."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

ARCHIVE_NAME = "Vib_ID_Account_Portal_v1.2.2_OPERATIONS_UI_PATCH.zip"
ROOT_PREFIX = "vib-id-account-portal"
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    "htmlcov",
    "playwright-report",
    "test-results",
    "audit-artifacts",
}
EXCLUDED_NAMES = {".env", ".coverage", ARCHIVE_NAME, f"{ARCHIVE_NAME}.sha256"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".log", ".zip", ".sha256"}


def include(path: Path) -> bool:
    relative = path.relative_to(Path.cwd())
    if any(part in EXCLUDED_DIRS for part in relative.parts):
        return False
    if path.name in EXCLUDED_NAMES:
        return False
    if path.name.startswith(".env.") and path.name != ".env.example":
        return False
    return path.suffix.lower() not in EXCLUDED_SUFFIXES


def main() -> None:
    root = Path.cwd()
    archive = root / ARCHIVE_NAME
    checksum = root / f"{ARCHIVE_NAME}.sha256"
    archive.unlink(missing_ok=True)
    checksum.unlink(missing_ok=True)

    files = sorted(path for path in root.rglob("*") if path.is_file() and include(path))
    fixed_timestamp = (2026, 7, 5, 0, 0, 0)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for path in files:
            relative = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo(f"{ROOT_PREFIX}/{relative}", date_time=fixed_timestamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if path.stat().st_mode & 0o111 else 0o644) << 16
            output.writestr(info, path.read_bytes())

    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksum.write_text(f"{digest}  {ARCHIVE_NAME}\n", encoding="utf-8")
    print(f"Created {archive.name} ({len(files)} files)")
    print(f"SHA-256: {digest}")


if __name__ == "__main__":
    main()
