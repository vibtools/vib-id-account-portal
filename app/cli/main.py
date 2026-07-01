"""Operational CLI for service registry, retention cleanup, and diagnostics."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import typer
from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.models.security import (
    LogoutTokenReplay,
    OIDCTransaction,
    PortalSession,
    RateLimitBucket,
    SecurityActivity,
)
from app.database.models.service import ServiceRegistry
from app.database.session import Database
from app.services_registry.repository import list_services, upsert_service
from app.services_registry.service import validate_service_metadata

app = typer.Typer(help="Vib ID operational commands", no_args_is_help=True)
service_app = typer.Typer(help="Manage the internal service registry", no_args_is_help=True)
app.add_typer(service_app, name="service")


async def _with_database[T](callback: Callable[[AsyncSession], Awaitable[T]]) -> T:
    database = Database(get_settings())
    try:
        async with database.session_factory() as db:
            try:
                result = await callback(db)
                await db.commit()
                return result
            except Exception:
                await db.rollback()
                raise
    finally:
        await database.dispose()


@service_app.command("register")
def register_service(
    service_key: str = typer.Option(...),
    display_name: str = typer.Option(...),
    domain: str = typer.Option(...),
    description: str = typer.Option(...),
    icon_reference: str | None = typer.Option(None),
    sort_order: int = typer.Option(100, min=0),
    active: bool = typer.Option(True),
) -> None:
    validate_service_metadata(
        service_key=service_key,
        display_name=display_name,
        domain=domain,
        description=description,
        icon_reference=icon_reference,
        sort_order=sort_order,
    )

    async def execute(db: AsyncSession) -> str:
        service = await upsert_service(
            db,
            service_key=service_key,
            display_name=display_name,
            domain=domain,
            description=description,
            icon_reference=icon_reference,
            active=active,
            sort_order=sort_order,
        )
        return str(service.id)

    identifier = asyncio.run(_with_database(execute))
    typer.echo(f"Service registered: {identifier}")


@service_app.command("deactivate")
def deactivate_service(service_key: str) -> None:
    async def execute(db: AsyncSession) -> bool:
        service = (
            await db.execute(
                select(ServiceRegistry).where(ServiceRegistry.service_key == service_key)
            )
        ).scalar_one_or_none()
        if service is None:
            return False
        service.active = False
        return True

    if not asyncio.run(_with_database(execute)):
        raise typer.BadParameter("service not found")
    typer.echo("Service deactivated")


@service_app.command("list")
def list_registered_services() -> None:
    async def execute(db: AsyncSession) -> list[ServiceRegistry]:
        return await list_services(db)

    services = asyncio.run(_with_database(execute))
    for service in services:
        state = "active" if service.active else "inactive"
        typer.echo(f"{service.service_key}\t{service.domain}\t{state}")


@app.command("cleanup")
def cleanup_retained_data() -> None:
    settings = get_settings()
    now = datetime.now(UTC)

    async def execute(db: AsyncSession) -> dict[str, int]:
        statements = {
            "activity": delete(SecurityActivity).where(
                SecurityActivity.occurred_at
                < now - timedelta(days=settings.SECURITY_ACTIVITY_RETENTION_DAYS)
            ),
            "sessions": delete(PortalSession).where(
                PortalSession.revoked_at.is_not(None),
                PortalSession.revoked_at
                < now - timedelta(days=settings.REVOKED_SESSION_RETENTION_DAYS),
            ),
            "oidc_transactions": delete(OIDCTransaction).where(OIDCTransaction.expires_at < now),
            "logout_replays": delete(LogoutTokenReplay).where(LogoutTokenReplay.expires_at < now),
            "rate_limits": delete(RateLimitBucket).where(RateLimitBucket.expires_at < now),
        }
        counts: dict[str, int] = {}
        for name, statement in statements.items():
            result = await db.execute(statement)
            counts[name] = int(cast(CursorResult[Any], result).rowcount or 0)
        return counts

    counts = asyncio.run(_with_database(execute))
    for name, count in counts.items():
        typer.echo(f"{name}: {count}")


if __name__ == "__main__":
    app()
