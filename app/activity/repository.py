"""User-isolated activity queries."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.security import SecurityActivity


async def list_activity(
    db: AsyncSession,
    *,
    subject: str,
    page: int,
    page_size: int = 20,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> tuple[list[SecurityActivity], int]:
    filters = [SecurityActivity.subject == subject]
    if date_from:
        filters.append(SecurityActivity.occurred_at >= date_from)
    if date_to:
        filters.append(SecurityActivity.occurred_at <= date_to)
    total = int(await db.scalar(select(func.count(SecurityActivity.id)).where(*filters)) or 0)
    result = await db.execute(
        select(SecurityActivity)
        .where(*filters)
        .order_by(SecurityActivity.occurred_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.scalars()), total


async def latest_activity(db: AsyncSession, subject: str) -> SecurityActivity | None:
    return (
        await db.execute(
            select(SecurityActivity)
            .where(SecurityActivity.subject == subject)
            .order_by(SecurityActivity.occurred_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
