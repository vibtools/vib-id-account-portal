"""PostgreSQL transaction-scoped advisory locks for first-write races."""

from __future__ import annotations

import hashlib

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def advisory_lock_key(namespace: str, identity: str) -> int:
    """Return a deterministic signed 64-bit PostgreSQL advisory-lock key."""
    digest = hashlib.sha256(f"{namespace}:{identity}".encode()).digest()[:8]
    return int.from_bytes(digest, byteorder="big", signed=True)


async def acquire_advisory_xact_lock(
    db: AsyncSession,
    *,
    namespace: str,
    identity: str,
) -> None:
    """Serialize one logical key for the current PostgreSQL transaction.

    SQLite is used only by the deterministic test suite and does not support
    advisory locks, so the helper intentionally becomes a no-op there.
    """
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return
    await db.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": advisory_lock_key(namespace, identity)},
    )
