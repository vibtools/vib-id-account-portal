"""Service registry domain validation."""

from __future__ import annotations

import re
from urllib.parse import urlparse

SERVICE_KEY = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
DOMAIN = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


def validate_service_metadata(
    *,
    service_key: str,
    display_name: str,
    domain: str,
    description: str,
    icon_reference: str | None,
    sort_order: int,
) -> None:
    if not SERVICE_KEY.fullmatch(service_key):
        raise ValueError("service_key must be lowercase kebab-case")
    if not DOMAIN.fullmatch(domain.lower()):
        raise ValueError("domain must be a valid hostname")
    if not 1 <= len(display_name.strip()) <= 100:
        raise ValueError("display_name length is invalid")
    if not 1 <= len(description.strip()) <= 280:
        raise ValueError("description length is invalid")
    if not 0 <= sort_order <= 100000:
        raise ValueError("sort_order is invalid")
    if icon_reference:
        parsed = urlparse(icon_reference)
        if parsed.scheme or parsed.netloc or icon_reference.startswith(("/", "..")):
            raise ValueError("icon_reference must be a safe local relative path")
