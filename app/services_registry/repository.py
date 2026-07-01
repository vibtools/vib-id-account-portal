"""Service registry persistence and read-only user connection queries."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database.base import as_utc
from app.database.locks import acquire_advisory_xact_lock
from app.database.models.enums import ConnectionStatus
from app.database.models.service import ServiceRegistry, UserServiceConnection


async def list_user_connections(db: AsyncSession, subject: str) -> list[UserServiceConnection]:
    result = await db.execute(
        select(UserServiceConnection)
        .options(joinedload(UserServiceConnection.service))
        .join(ServiceRegistry)
        .where(
            UserServiceConnection.subject == subject,
            ServiceRegistry.active.is_(True),
        )
        .order_by(ServiceRegistry.sort_order, ServiceRegistry.display_name)
    )
    return list(result.scalars().unique())


async def touch_connection(
    db: AsyncSession,
    *,
    subject: str,
    service_key: str,
    authenticated_at: datetime,
) -> tuple[UserServiceConnection, bool]:
    await acquire_advisory_xact_lock(
        db,
        namespace="service-connection",
        identity=f"{subject}:{service_key}",
    )
    service = (
        await db.execute(
            select(ServiceRegistry).where(
                ServiceRegistry.service_key == service_key,
                ServiceRegistry.active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if service is None:
        raise LookupError("service is not registered or inactive")
    connection = (
        await db.execute(
            select(UserServiceConnection).where(
                UserServiceConnection.subject == subject,
                UserServiceConnection.service_id == service.id,
            )
        )
    ).scalar_one_or_none()
    timestamp = authenticated_at.astimezone(UTC)
    created = connection is None
    if connection is None:
        connection = UserServiceConnection(
            subject=subject,
            service_id=service.id,
            first_connected_at=timestamp,
            last_authenticated_at=timestamp,
            current_status=ConnectionStatus.ACTIVE,
            connection_metadata={},
        )
        db.add(connection)
    elif timestamp > as_utc(connection.last_authenticated_at):
        connection.last_authenticated_at = timestamp
        connection.current_status = ConnectionStatus.ACTIVE
    await db.flush()
    return connection, created


async def upsert_service(
    db: AsyncSession,
    *,
    service_key: str,
    display_name: str,
    domain: str,
    description: str,
    icon_reference: str | None,
    active: bool,
    sort_order: int,
) -> ServiceRegistry:
    service = (
        await db.execute(select(ServiceRegistry).where(ServiceRegistry.service_key == service_key))
    ).scalar_one_or_none()
    if service is None:
        service = ServiceRegistry(service_key=service_key)
        db.add(service)
    service.display_name = display_name
    service.domain = domain.lower()
    service.description = description
    service.icon_reference = icon_reference
    service.active = active
    service.sort_order = sort_order
    await db.flush()
    return service


async def list_services(db: AsyncSession) -> list[ServiceRegistry]:
    return list(
        (
            await db.execute(
                select(ServiceRegistry).order_by(
                    ServiceRegistry.sort_order, ServiceRegistry.display_name
                )
            )
        ).scalars()
    )
