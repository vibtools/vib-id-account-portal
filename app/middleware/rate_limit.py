"""Cross-instance fixed-window PostgreSQL rate limiter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.base import as_utc
from app.database.locks import acquire_advisory_xact_lock
from app.database.models.security import RateLimitBucket
from app.security.identifiers import sha256_text


@dataclass(frozen=True, slots=True)
class RateLimit:
    requests: int
    window_seconds: int


class RateLimitExceeded(RuntimeError):
    def __init__(self, retry_after: int) -> None:
        super().__init__("rate limit exceeded")
        self.retry_after = max(1, retry_after)


class DatabaseRateLimiter:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    async def enforce(
        self,
        db: AsyncSession,
        *,
        namespace: str,
        identity: str,
        limit: RateLimit,
        now: datetime | None = None,
    ) -> None:
        if not self.enabled:
            return
        current = now or datetime.now(UTC)
        key_hash = sha256_text(f"{namespace}:{identity}")
        await acquire_advisory_xact_lock(
            db,
            namespace="rate-limit",
            identity=key_hash,
        )
        statement = (
            select(RateLimitBucket).where(RateLimitBucket.key_hash == key_hash).with_for_update()
        )
        bucket = (await db.execute(statement)).scalar_one_or_none()
        if bucket is None or as_utc(bucket.expires_at) <= current:
            expires = current + timedelta(seconds=limit.window_seconds)
            if bucket is None:
                bucket = RateLimitBucket(
                    key_hash=key_hash,
                    window_started_at=current,
                    request_count=1,
                    expires_at=expires,
                )
                db.add(bucket)
            else:
                bucket.window_started_at = current
                bucket.request_count = 1
                bucket.expires_at = expires
            await db.flush()
            return
        if bucket.request_count >= limit.requests:
            retry_after = int((as_utc(bucket.expires_at) - current).total_seconds()) + 1
            raise RateLimitExceeded(retry_after)
        bucket.request_count += 1
        await db.flush()

    async def cleanup(self, db: AsyncSession, now: datetime | None = None) -> int:
        current = now or datetime.now(UTC)
        result = await db.execute(
            delete(RateLimitBucket).where(RateLimitBucket.expires_at < current)
        )
        return int(cast(CursorResult[Any], result).rowcount or 0)
