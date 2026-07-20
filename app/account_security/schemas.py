"""Schemas used by the Vib ID account-security module."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProfileSummary(BaseModel):
    subject: str
    display_name: str | None = None
    email: str | None = None
    email_verified: bool | None = None
    preferred_username: str | None = None


class SecurityStatus(BaseModel):
    account_enabled: bool | None
    email_verified: bool | None
    two_factor_enabled: bool | None
    central_session_count: int | None
    central_available: bool


class SessionSummary(BaseModel):
    id: str
    current: bool
    device_label: str
    user_agent_summary: str
    created_at: datetime
    last_seen_at: datetime
    idle_expires_at: datetime
    absolute_expires_at: datetime


class CentralSessionSummary(BaseModel):
    id: str
    username: str | None = None
    ip_address: str | None = None
    started: int | None = None
    last_access: int | None = None
    clients: list[str] = Field(default_factory=list)


class ApplicationSummary(BaseModel):
    service_key: str
    display_name: str
    domain: str
    description: str
    status: str
    source: str = "registry"
    first_connected_at: datetime | None = None
    last_authenticated_at: datetime | None = None
    catalog_visible: bool = False
