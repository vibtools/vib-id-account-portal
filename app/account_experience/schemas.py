"""Portable profile schemas for Vib ID connected applications."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class PortableSocialLink(BaseModel):
    platform: str
    label: str
    url: HttpUrl


class PortableProfile(BaseModel):
    subject: str
    display_name: str | None = None
    preferred_username: str | None = None
    email: str | None = None
    email_verified: bool | None = None
    preferred_language: str | None = None
    timezone: str | None = None
    country_code: str | None = None
    organization_name: str | None = None
    job_title: str | None = None
    avatar_url: str | None = None
    social_links: list[PortableSocialLink] = Field(default_factory=list)
    updated_at: datetime | None = None
