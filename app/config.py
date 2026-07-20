"""Strict application configuration."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_SECRET_VALUES = {
    "changeme",
    "change-me",
    "secret",
    "password",
    "development",
    "insecure",
}


class Settings(BaseSettings):
    """Environment-backed settings with fail-closed production validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    APP_ENV: Literal["development", "test", "production"] = "production"
    APP_NAME: str = "Vib ID"
    APP_BASE_URL: str = "https://id.vib.tools"
    APP_SECRET_KEY: SecretStr
    TOKEN_ENCRYPTION_KEY: SecretStr
    DATABASE_URL: str
    OIDC_ISSUER_URL: str = "https://auth.vib.tools/realms/vib"
    OIDC_CLIENT_ID: str = "vib-id-portal"
    OIDC_CLIENT_SECRET: SecretStr
    OIDC_REDIRECT_URI: str = "https://id.vib.tools/auth/callback"
    OIDC_POST_LOGOUT_REDIRECT_URI: str = "https://id.vib.tools/"
    OIDC_SCOPES: str = "openid profile email"
    OIDC_EXPECTED_AUDIENCE: str = "vib-id-portal"
    OIDC_HTTP_TIMEOUT_SECONDS: float = Field(default=5.0, ge=1.0, le=30.0)
    OIDC_CLOCK_SKEW_SECONDS: int = Field(default=30, ge=0, le=120)

    KEYCLOAK_MANAGEMENT_CLIENT_ID: str = "vib-id-portal-management"
    KEYCLOAK_MANAGEMENT_CLIENT_SECRET: SecretStr
    KEYCLOAK_MANAGEMENT_AUDIENCE: str = "account"
    KEYCLOAK_ACCOUNT_URL: str = "https://auth.vib.tools/realms/vib/account/"
    KEYCLOAK_ALLOWED_INTERNAL_CLIENTS: str = ""
    INTERNAL_REQUIRED_ROLE: str = "service-connections:touch"

    SESSION_COOKIE_NAME: str = "__Host-vib_id_session"
    SESSION_IDLE_MINUTES: int = Field(default=30, ge=5, le=1440)
    SESSION_ABSOLUTE_HOURS: int = Field(default=12, ge=1, le=168)
    SESSION_MAX_CONCURRENT: int = Field(default=10, ge=1, le=50)
    SESSION_COOKIE_SECURE: bool = True
    SESSION_COOKIE_SAMESITE: Literal["lax", "strict"] = "lax"

    SECURITY_ACTIVITY_RETENTION_DAYS: int = Field(default=180, ge=30, le=2555)
    REVOKED_SESSION_RETENTION_DAYS: int = Field(default=30, ge=1, le=365)
    TRUSTED_HOSTS: str = "id.vib.tools"
    CSRF_SECRET: SecretStr
    IP_PRIVACY_KEY: SecretStr
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    DATABASE_POOL_SIZE: int = Field(default=5, ge=1, le=30)
    DATABASE_MAX_OVERFLOW: int = Field(default=5, ge=0, le=30)
    DATABASE_POOL_TIMEOUT: int = Field(default=10, ge=1, le=60)
    PROFILE_CONTACT_LIMIT: int = Field(default=10, ge=1, le=25)
    RATE_LIMIT_ENABLED: bool = True
    REQUEST_BODY_MAX_BYTES: int = Field(default=3 * 1024 * 1024, ge=64 * 1024, le=8 * 1024 * 1024)
    PROFILE_AVATAR_MAX_BYTES: int = Field(default=1 * 1024 * 1024, ge=16 * 1024, le=2 * 1024 * 1024)
    PROFILE_AVATAR_ALLOWED_TYPES: str = "image/png,image/jpeg,image/webp"


    @field_validator(
        "APP_SECRET_KEY",
        "OIDC_CLIENT_SECRET",
        "KEYCLOAK_MANAGEMENT_CLIENT_SECRET",
        "CSRF_SECRET",
        "IP_PRIVACY_KEY",
    )
    @classmethod
    def validate_long_secret(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if len(raw) < 32 or raw.lower() in INSECURE_SECRET_VALUES:
            raise ValueError("secret must contain at least 32 non-default characters")
        return value

    @field_validator("TOKEN_ENCRYPTION_KEY")
    @classmethod
    def validate_fernet_key(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}=", raw):
            raise ValueError("TOKEN_ENCRYPTION_KEY must be a URL-safe base64 Fernet key")
        return value

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not value.startswith(("postgresql+asyncpg://", "sqlite+aiosqlite://")):
            raise ValueError("DATABASE_URL must use postgresql+asyncpg or sqlite+aiosqlite")
        return value

    @field_validator("OIDC_SCOPES")
    @classmethod
    def validate_scopes(cls, value: str) -> str:
        scopes = set(value.split())
        required = {"openid", "profile", "email"}
        if not required.issubset(scopes):
            raise ValueError("OIDC_SCOPES must contain openid profile email")
        return " ".join(dict.fromkeys(value.split()))

    @field_validator("TRUSTED_HOSTS")
    @classmethod
    def validate_hosts(cls, value: str) -> str:
        hosts = [host.strip() for host in value.split(",") if host.strip()]
        if not hosts or "*" in hosts:
            raise ValueError("TRUSTED_HOSTS must be a non-empty explicit allowlist")
        return ",".join(hosts)

    @model_validator(mode="after")
    def validate_environment_security(self) -> Settings:
        base = urlparse(self.APP_BASE_URL)
        issuer = urlparse(self.OIDC_ISSUER_URL)
        redirect = urlparse(self.OIDC_REDIRECT_URI)
        logout_redirect = urlparse(self.OIDC_POST_LOGOUT_REDIRECT_URI)
        account = urlparse(self.KEYCLOAK_ACCOUNT_URL)

        if self.APP_ENV == "production":
            urls = (base, issuer, redirect, logout_redirect, account)
            if any(parsed.scheme != "https" for parsed in urls):
                raise ValueError("all production public URLs must use HTTPS")
            if not self.SESSION_COOKIE_SECURE:
                raise ValueError("secure cookies cannot be disabled in production")
            if not self.DATABASE_URL.startswith("postgresql+asyncpg://"):
                raise ValueError("production DATABASE_URL must use PostgreSQL with asyncpg")
            if issuer.hostname != "auth.vib.tools":
                raise ValueError("production OIDC issuer host must be auth.vib.tools")
            if base.hostname != "id.vib.tools":
                raise ValueError("production portal host must be id.vib.tools")

        if redirect.geturl() != f"{self.APP_BASE_URL.rstrip('/')}/auth/callback":
            raise ValueError("OIDC_REDIRECT_URI must exactly match the portal callback URL")
        if logout_redirect.hostname != base.hostname:
            raise ValueError("post-logout redirect host must match APP_BASE_URL")
        if account.hostname != issuer.hostname:
            raise ValueError("Keycloak account URL host must match issuer host")
        return self

    @property
    def allowed_profile_avatar_types(self) -> set[str]:
        return {
            item.strip().lower()
            for item in self.PROFILE_AVATAR_ALLOWED_TYPES.split(",")
            if item.strip()
        }

    @property
    def trusted_hosts(self) -> list[str]:
        return [host.strip() for host in self.TRUSTED_HOSTS.split(",") if host.strip()]

    @property
    def allowed_internal_clients(self) -> frozenset[str]:
        return frozenset(
            item.strip()
            for item in self.KEYCLOAK_ALLOWED_INTERNAL_CLIENTS.split(",")
            if item.strip()
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
