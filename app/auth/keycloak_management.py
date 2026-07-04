"""Least-privilege Keycloak management client with bounded failure behavior."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlencode

import httpx

from app.auth.token_validation import OIDCValidator
from app.config import Settings


class KeycloakUnavailable(RuntimeError):
    pass


@dataclass(slots=True)
class CentralAccountStatus:
    enabled: bool | None
    email_verified: bool | None
    two_factor_enabled: bool | None
    session_count: int | None
    available: bool


class KeycloakManagementClient:
    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient,
        validator: OIDCValidator,
    ) -> None:
        self.settings = settings
        self.client = client
        self.validator = validator
        self._access_token: str | None = None
        self._token_expires_at = 0.0
        self._lock = asyncio.Lock()
        self._failures = 0
        self._circuit_open_until = 0.0

    @property
    def realm(self) -> str:
        return self.settings.OIDC_ISSUER_URL.rstrip("/").rsplit("/", 1)[-1]

    @property
    def admin_base(self) -> str:
        issuer = self.settings.OIDC_ISSUER_URL.rstrip("/")
        root = issuer.split("/realms/", 1)[0]
        return f"{root}/admin/realms/{quote(self.realm, safe='')}"

    async def account_status(self, subject: str) -> CentralAccountStatus:
        try:
            user = await self._request("GET", f"/users/{quote(subject, safe='')}")
            credentials = await self._request(
                "GET", f"/users/{quote(subject, safe='')}/credentials"
            )
            sessions = await self._request("GET", f"/users/{quote(subject, safe='')}/sessions")
            two_factor = any(
                isinstance(item, dict) and item.get("type") == "otp"
                for item in credentials
                if isinstance(credentials, list)
            )
            return CentralAccountStatus(
                enabled=bool(user.get("enabled")) if isinstance(user, dict) else None,
                email_verified=(
                    bool(user.get("emailVerified")) if isinstance(user, dict) else None
                ),
                two_factor_enabled=two_factor,
                session_count=len(sessions) if isinstance(sessions, list) else None,
                available=True,
            )
        except KeycloakUnavailable:
            return CentralAccountStatus(None, None, None, None, False)

    async def revoke_central_session(self, subject: str, session_id: str) -> bool:
        sessions = await self._request("GET", f"/users/{quote(subject, safe='')}/sessions")
        allowed_ids = {
            str(item.get("id")) for item in sessions if isinstance(item, dict) and item.get("id")
        }
        if session_id not in allowed_ids:
            return False
        await self._request("DELETE", f"/sessions/{quote(session_id, safe='')}")
        return True

    async def logout_user(self, subject: str) -> None:
        await self._request("POST", f"/users/{quote(subject, safe='')}/logout")

    async def _get_management_token(self) -> str:
        if self._access_token and time.monotonic() < self._token_expires_at - 15:
            return self._access_token
        async with self._lock:
            if self._access_token and time.monotonic() < self._token_expires_at - 15:
                return self._access_token
            metadata = await self.validator.metadata()
            response = await self.client.post(
                metadata.token_endpoint,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.settings.KEYCLOAK_MANAGEMENT_CLIENT_ID,
                    "client_secret": (
                        self.settings.KEYCLOAK_MANAGEMENT_CLIENT_SECRET.get_secret_value()
                    ),
                },
            )
            if response.status_code != 200:
                self._record_failure()
                raise KeycloakUnavailable("management token request failed")
            try:
                payload = response.json()
            except ValueError as exc:
                self._record_failure()
                raise KeycloakUnavailable("management token response invalid") from exc
            token = payload.get("access_token")
            if not isinstance(token, str):
                self._record_failure()
                raise KeycloakUnavailable("management token response invalid")
            self._access_token = token
            self._token_expires_at = time.monotonic() + int(payload.get("expires_in", 60))
            self._record_success()
            return token

    async def get_user(self, subject: str) -> dict[str, Any]:
        user = await self._request("GET", f"/users/{quote(subject, safe='')}")
        return user if isinstance(user, dict) else {}

    async def update_user_email(
        self,
        subject: str,
        email: str,
        *,
        redirect_uri: str | None = None,
    ) -> None:
        user = await self.get_user(subject)
        if not user:
            raise KeycloakUnavailable("user not found")
        payload = {
            "id": user.get("id", subject),
            "username": user.get("username"),
            "firstName": user.get("firstName"),
            "lastName": user.get("lastName"),
            "email": email,
            "enabled": user.get("enabled", True),
            "emailVerified": False,
            "attributes": user.get("attributes", {}),
        }
        await self._request("PUT", f"/users/{quote(subject, safe='')}", json=payload)
        await self.send_verify_email(subject, redirect_uri=redirect_uri)

    async def send_verify_email(self, subject: str, *, redirect_uri: str | None = None) -> None:
        params: dict[str, str] = {"client_id": self.settings.OIDC_CLIENT_ID}
        if redirect_uri:
            params["redirect_uri"] = redirect_uri
        query = urlencode(params)
        await self._request(
            "PUT",
            f"/users/{quote(subject, safe='')}/send-verify-email?{query}",
        )

    async def execute_required_actions_email(
        self,
        subject: str,
        *,
        actions: list[str],
        redirect_uri: str | None = None,
        lifespan_seconds: int = 600,
    ) -> None:
        allowed_actions = {"UPDATE_PASSWORD", "CONFIGURE_TOTP", "VERIFY_EMAIL", "UPDATE_PROFILE"}
        safe_actions = [action for action in actions if action in allowed_actions]
        if not safe_actions:
            raise KeycloakUnavailable("no supported required actions requested")
        params: dict[str, str] = {
            "client_id": self.settings.OIDC_CLIENT_ID,
            "lifespan": str(max(60, min(lifespan_seconds, 3600))),
        }
        if redirect_uri:
            params["redirect_uri"] = redirect_uri
        query = urlencode(params)
        await self._request(
            "PUT",
            f"/users/{quote(subject, safe='')}/execute-actions-email?{query}",
            json=safe_actions,
        )

    async def list_user_sessions(self, subject: str) -> list[dict[str, Any]]:
        sessions = await self._request("GET", f"/users/{quote(subject, safe='')}/sessions")
        if not isinstance(sessions, list):
            return []
        return [item for item in sessions if isinstance(item, dict)]

    async def list_user_credentials(self, subject: str) -> list[dict[str, Any]]:
        credentials = await self._request("GET", f"/users/{quote(subject, safe='')}/credentials")
        if not isinstance(credentials, list):
            return []
        return [item for item in credentials if isinstance(item, dict)]

    async def remove_totp_credentials(self, subject: str) -> bool:
        removed = False
        for credential in await self.list_user_credentials(subject):
            if credential.get("type") == "otp" and credential.get("id"):
                await self._request(
                    "DELETE",
                    (
                        f"/users/{quote(subject, safe='')}/credentials/"
                        f"{quote(str(credential['id']), safe='')}"
                    ),
                )
                removed = True
        return removed

    async def list_user_consents(self, subject: str) -> list[dict[str, Any]]:
        consents = await self._request("GET", f"/users/{quote(subject, safe='')}/consents")
        if not isinstance(consents, list):
            return []
        return [item for item in consents if isinstance(item, dict)]

    async def revoke_user_consent(self, subject: str, client_id: str) -> bool:
        consents = await self.list_user_consents(subject)
        allowed = {str(item.get("clientId")) for item in consents if item.get("clientId")}
        if client_id not in allowed:
            return False
        await self._request(
            "DELETE",
            f"/users/{quote(subject, safe='')}/consents/{quote(client_id, safe='')}",
        )
        return True

    async def _request(self, method: str, path: str, *, json: object | None = None) -> Any:
        if time.monotonic() < self._circuit_open_until:
            raise KeycloakUnavailable("management circuit is open")
        token = await self._get_management_token()
        url = f"{self.admin_base}{path}"
        try:
            response = await self.client.request(
                method,
                url,
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                json=json,
            )
            if response.status_code == 401:
                self._access_token = None
            if response.status_code not in {200, 201, 204}:
                self._record_failure()
                raise KeycloakUnavailable("management request failed")
            self._record_success()
            if response.status_code == 204:
                return None
            try:
                return response.json()
            except ValueError as exc:
                self._record_failure()
                raise KeycloakUnavailable("management response invalid") from exc
        except httpx.HTTPError as exc:
            self._record_failure()
            raise KeycloakUnavailable("management service unavailable") from exc

    def _record_failure(self) -> None:
        self._failures += 1
        if self._failures >= 3:
            self._circuit_open_until = time.monotonic() + 30

    def _record_success(self) -> None:
        self._failures = 0
        self._circuit_open_until = 0.0
