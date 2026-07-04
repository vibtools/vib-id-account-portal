"""Service helpers for the native Vib ID account-security module."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.account_security.schemas import (
    ApplicationSummary,
    CentralSessionSummary,
    ProfileSummary,
    SecurityStatus,
    SessionSummary,
)
from app.accounts.repository import get_profile
from app.auth.keycloak_management import CentralAccountStatus, KeycloakUnavailable
from app.auth.sessions import AuthenticatedSession
from app.services_registry.repository import list_user_connections


def claims_from_auth(auth: AuthenticatedSession) -> dict[str, Any]:
    claims = auth.token_bundle.get("_id_claims", {})
    return claims if isinstance(claims, dict) else {}


async def profile_summary(db: AsyncSession, auth: AuthenticatedSession) -> ProfileSummary:
    claims = claims_from_auth(auth)
    profile = await get_profile(db, auth.subject)
    display_name = profile.display_name if profile is not None else None
    return ProfileSummary(
        subject=auth.subject,
        display_name=display_name or _optional_str(claims.get("name")),
        email=_optional_str(claims.get("email")),
        email_verified=_optional_bool(claims.get("email_verified")),
        preferred_username=_optional_str(claims.get("preferred_username")),
    )


def security_status_from_central(
    central: CentralAccountStatus,
    *,
    token_email_verified: bool | None,
) -> SecurityStatus:
    return SecurityStatus(
        account_enabled=central.enabled,
        email_verified=(
            central.email_verified if central.email_verified is not None else token_email_verified
        ),
        two_factor_enabled=central.two_factor_enabled,
        central_session_count=central.session_count,
        central_available=central.available,
    )


def local_session_summaries(
    auth: AuthenticatedSession, sessions: Iterable[Any]
) -> list[SessionSummary]:
    return [
        SessionSummary(
            id=str(item.id),
            current=item.id == auth.model.id,
            device_label=str(item.device_label),
            user_agent_summary=str(item.user_agent_summary),
            created_at=item.created_at,
            last_seen_at=item.last_seen_at,
            idle_expires_at=item.idle_expires_at,
            absolute_expires_at=item.absolute_expires_at,
        )
        for item in sessions
    ]


def central_session_summaries(
    raw_sessions: Iterable[dict[str, Any]],
) -> list[CentralSessionSummary]:
    summaries: list[CentralSessionSummary] = []
    for item in raw_sessions:
        clients_raw = item.get("clients")
        clients: list[str] = []
        if isinstance(clients_raw, dict):
            clients = [str(value) for value in clients_raw.values() if value]
        elif isinstance(clients_raw, list):
            clients = [str(value) for value in clients_raw if value]
        summaries.append(
            CentralSessionSummary(
                id=str(item.get("id", "")),
                username=_optional_str(item.get("username")),
                ip_address=_optional_str(item.get("ipAddress")),
                started=_optional_int(item.get("start")),
                last_access=_optional_int(item.get("lastAccess")),
                clients=clients,
            )
        )
    return [item for item in summaries if item.id]


async def application_summaries(db: AsyncSession, subject: str) -> list[ApplicationSummary]:
    connections = await list_user_connections(db, subject)
    return [
        ApplicationSummary(
            service_key=str(connection.service.service_key),
            display_name=str(connection.service.display_name),
            domain=str(connection.service.domain),
            description=str(connection.service.description),
            status=str(connection.current_status.value),
            first_connected_at=connection.first_connected_at,
            last_authenticated_at=connection.last_authenticated_at,
        )
        for connection in connections
    ]


async def safe_central_sessions(keycloak: Any, subject: str) -> list[dict[str, Any]]:
    method = getattr(keycloak, "list_user_sessions", None)
    if not callable(method):
        return []
    try:
        result = await method(subject)
    except KeycloakUnavailable:
        return []
    if not isinstance(result, list):
        return []
    return [item for item in result if isinstance(item, dict)]


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None
