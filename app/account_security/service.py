"""Service helpers for the native Vib ID account-security module."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import UTC, datetime
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
from app.database.base import as_utc
from app.services_registry.repository import (
    canonical_service_key,
    catalog_service_definitions,
    default_service_definition,
    list_user_connections,
)


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


async def application_summaries(
    db: AsyncSession,
    subject: str,
    *,
    central_sessions: Iterable[dict[str, Any]] | None = None,
) -> list[ApplicationSummary]:
    connections = await list_user_connections(db, subject)
    summaries: dict[str, ApplicationSummary] = {}
    for connection in connections:
        service_key = str(connection.service.service_key)
        existing_key = _find_existing_service_key(summaries, service_key)
        if existing_key is not None:
            existing = summaries[existing_key]
            existing.first_connected_at = _earliest_datetime(
                existing.first_connected_at, connection.first_connected_at
            )
            existing.last_authenticated_at = _latest_datetime(
                existing.last_authenticated_at, connection.last_authenticated_at
            )
            existing.status = str(connection.current_status.value)
            continue
        display_name = str(connection.service.display_name)
        domain = str(connection.service.domain)
        description = str(connection.service.description)
        summaries[service_key] = ApplicationSummary(
            service_key=service_key,
            display_name=display_name,
            domain=domain,
            description=description,
            status=str(connection.current_status.value),
            source="registry",
            first_connected_at=connection.first_connected_at,
            last_authenticated_at=connection.last_authenticated_at,
        )
    for client_id, last_access in _central_client_ids(central_sessions or []):
        if client_id in {"vib-id-portal", "account", "realm-management"}:
            continue
        service_key = canonical_service_key(client_id)
        definition = default_service_definition(service_key)
        if definition is None:
            continue
        last_authenticated_at = _millis_to_datetime(last_access)
        existing_key = _find_existing_service_key(summaries, service_key)
        if existing_key is not None:
            existing = summaries[existing_key]
            existing.status = "active"
            existing.source = (
                "registry_and_central_session"
                if existing.source == "registry"
                else existing.source
            )
            existing.last_authenticated_at = _latest_datetime(
                existing.last_authenticated_at, last_authenticated_at
            )
            continue
        summaries[service_key] = ApplicationSummary(
            service_key=service_key,
            display_name=str(definition["display_name"]),
            domain=str(definition["domain"]),
            description=str(definition["description"]),
            status="active",
            source="central_session",
            first_connected_at=None,
            last_authenticated_at=last_authenticated_at,
        )
    return sorted(summaries.values(), key=lambda item: (item.domain, item.display_name))


def application_catalog_summaries(
    connected_summaries: Iterable[ApplicationSummary] | None = None,
) -> list[ApplicationSummary]:
    """Return first-class VibTools apps even before the first service touch."""

    connected_items = list(connected_summaries or [])
    catalog: list[ApplicationSummary] = []
    for service_key, definition in catalog_service_definitions().items():
        connected = next(
            (
                item
                for item in connected_items
                if canonical_service_key(item.service_key) == service_key
            ),
            None,
        )
        if connected is not None:
            catalog.append(connected.model_copy(update={"catalog_visible": True}))
            continue
        catalog.append(
            ApplicationSummary(
                service_key=service_key,
                display_name=str(definition["display_name"]),
                domain=str(definition["domain"]),
                description=str(definition["description"]),
                status="available",
                source="catalog",
                first_connected_at=None,
                last_authenticated_at=None,
                catalog_visible=True,
            )
        )
    return catalog


def _find_existing_service_key(
    summaries: dict[str, ApplicationSummary], service_key: str
) -> str | None:
    if service_key in summaries:
        return service_key
    canonical_key = canonical_service_key(service_key)
    for candidate in summaries:
        if canonical_service_key(candidate) == canonical_key:
            return candidate
    return None


def _central_client_ids(raw_sessions: Iterable[dict[str, Any]]) -> list[tuple[str, int | None]]:
    found: list[tuple[str, int | None]] = []
    for item in raw_sessions:
        last_access = _optional_int(item.get("lastAccess"))
        clients = item.get("clients")
        if isinstance(clients, dict):
            for key, value in clients.items():
                found.extend(
                    (candidate, last_access)
                    for candidate in _client_candidates(key, value)
                )
        elif isinstance(clients, list):
            for value in clients:
                found.extend((candidate, last_access) for candidate in _client_candidates(value))
    return found


def _client_candidates(*values: object) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value:
            continue
        raw = str(value).strip()
        if not raw:
            continue
        normalized = _normalize_client_identifier(raw)
        aliases = [normalized, *_client_aliases(normalized)]
        for alias in aliases:
            if alias and alias not in seen:
                seen.add(alias)
                candidates.append(alias)
    return candidates


def _normalize_client_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")


def _client_aliases(normalized: str) -> list[str]:
    aliases: dict[str, list[str]] = {
        "ygit": ["ygit"],
        "ygit-net": ["ygit"],
        "ygit-net-backend": ["ygit", "ygit-net"],
        "ygit-backend": ["ygit"],
        "ygit-client": ["ygit"],
        "ygit-web": ["ygit"],
        "ygit-dev": ["ygit-dev"],
        "ygit-dev-backend": ["ygit-dev"],
        "ygit-dev-client": ["ygit-dev"],
        "ygit-dev-web": ["ygit-dev"],
    }
    if normalized.startswith("service-account-"):
        return _client_aliases(normalized.removeprefix("service-account-"))
    if normalized.startswith("client-"):
        return _client_aliases(normalized.removeprefix("client-"))
    return aliases.get(normalized, [])


def _millis_to_datetime(value: int | None) -> datetime | None:
    if value is None:
        return None
    # Keycloak user-session timestamps are millisecond epoch values.
    if value > 10_000_000_000:
        return datetime.fromtimestamp(value / 1000, UTC)
    return datetime.fromtimestamp(value, UTC)


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


def _latest_datetime(left: datetime | None, right: datetime | None) -> datetime | None:
    if left is None:
        return right
    if right is None:
        return left
    return max(as_utc(left), as_utc(right))


def _earliest_datetime(left: datetime | None, right: datetime | None) -> datetime | None:
    if left is None:
        return right
    if right is None:
        return left
    return min(as_utc(left), as_utc(right))
