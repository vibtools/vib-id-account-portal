from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.accounts.repository import (
    ConcurrentProfileUpdate,
    add_contact,
    ensure_account_records,
    update_profile,
)
from app.accounts.schemas import ContactCreate, ProfileUpdate
from app.database.models.enums import ContactType
from app.database.models.security import PortalSession
from app.middleware.rate_limit import DatabaseRateLimiter, RateLimit, RateLimitExceeded


def test_account_repository_contact_and_optimistic_concurrency(client) -> None:
    async def exercise() -> None:
        async with client.app.state.database.session_factory() as db:
            profile, _ = await ensure_account_records(
                db, subject="repo-user", display_name="Original"
            )
            await db.commit()
            await db.refresh(profile)
            payload = ProfileUpdate(
                display_name="Updated",
                timezone="UTC",
                preferred_language="en",
                version=profile.updated_at,
            )
            updated = await update_profile(db, subject="repo-user", payload=payload)
            assert updated.display_name == "Updated"
            stale = payload.model_copy(update={"version": profile.updated_at - timedelta(days=1)})
            with pytest.raises(ConcurrentProfileUpdate):
                await update_profile(db, subject="repo-user", payload=stale)
            contact = await add_contact(
                db,
                subject="repo-user",
                payload=ContactCreate(
                    contact_type=ContactType.EMAIL,
                    label="Work",
                    value="Repo@Example.com",
                    is_primary=True,
                ),
                contact_limit=2,
            )
            assert contact.normalized_value == "repo@example.com"
            await db.commit()

    asyncio.run(exercise())


def test_session_lifecycle_is_hashed_encrypted_and_subject_isolated(client) -> None:
    async def exercise() -> None:
        async with client.app.state.database.session_factory() as db:
            auth = await client.app.state.session_service.create(
                db,
                subject="session-user",
                token_bundle={"access_token": "secret-token"},
                user_agent="Firefox/100 Linux",
                ip_address="198.51.100.5",
                oidc_sid="sid-1",
            )
            await db.commit()
            row = (await db.execute(select(PortalSession))).scalar_one()
            assert row.session_hash != auth.raw_id
            assert b"secret-token" not in row.encrypted_token_bundle
            resolved = await client.app.state.session_service.resolve(db, auth.raw_id, touch=False)
            assert resolved is not None
            assert resolved.token_bundle["access_token"] == "secret-token"
            assert not await client.app.state.session_service.revoke(
                db, session_id=row.id, subject="different-user", reason="idor-attempt"
            )
            assert await client.app.state.session_service.revoke(
                db, session_id=row.id, subject="session-user", reason="test"
            )
            assert await client.app.state.session_service.resolve(db, auth.raw_id) is None

    asyncio.run(exercise())


def test_session_expiry_and_concurrent_limit(client) -> None:
    async def exercise() -> None:
        client.app.state.settings.SESSION_MAX_CONCURRENT = 2
        async with client.app.state.database.session_factory() as db:
            sessions = []
            for index in range(3):
                auth = await client.app.state.session_service.create(
                    db,
                    subject="limit-user",
                    token_bundle={"index": index},
                    user_agent="Chrome Windows",
                    ip_address="203.0.113.1",
                    oidc_sid=f"sid-{index}",
                )
                sessions.append(auth)
                await db.commit()
            active = await client.app.state.session_service.list_active(db, "limit-user")
            assert len(active) == 2
            sessions[-1].model.idle_expires_at = datetime.now(UTC) - timedelta(seconds=1)
            await db.commit()
            assert await client.app.state.session_service.resolve(db, sessions[-1].raw_id) is None

    asyncio.run(exercise())


def test_database_rate_limiter_enforces_and_resets(client) -> None:
    async def exercise() -> None:
        limiter = DatabaseRateLimiter(True)
        now = datetime.now(UTC)
        async with client.app.state.database.session_factory() as db:
            await limiter.enforce(
                db, namespace="unit", identity="user", limit=RateLimit(2, 10), now=now
            )
            await limiter.enforce(
                db, namespace="unit", identity="user", limit=RateLimit(2, 10), now=now
            )
            with pytest.raises(RateLimitExceeded):
                await limiter.enforce(
                    db, namespace="unit", identity="user", limit=RateLimit(2, 10), now=now
                )
            await limiter.enforce(
                db,
                namespace="unit",
                identity="user",
                limit=RateLimit(2, 10),
                now=now + timedelta(seconds=11),
            )
            await db.commit()
            assert await limiter.cleanup(db, now=now + timedelta(seconds=30)) == 1

    asyncio.run(exercise())
