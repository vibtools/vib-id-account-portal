"""Opaque identifiers, keyed privacy transforms, and safe client summaries."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import re
import secrets

CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def generate_opaque_token(size: int = 32) -> str:
    if size < 24:
        raise ValueError("opaque tokens require at least 192 bits")
    return secrets.token_urlsafe(size)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def privacy_ip(value: str | None, key: str) -> str:
    candidate = value or "unknown"
    try:
        normalized = ipaddress.ip_address(candidate).compressed
    except ValueError:
        normalized = "unknown"
    return hmac.new(key.encode("utf-8"), normalized.encode("utf-8"), hashlib.sha256).hexdigest()


def sanitize_user_agent(value: str | None, max_length: int = 255) -> str:
    cleaned = CONTROL_CHARS.sub("", value or "Unknown client").strip()
    return (cleaned or "Unknown client")[:max_length]


def device_label(user_agent: str) -> str:
    lowered = user_agent.lower()
    browser = "Browser"
    if "edg/" in lowered:
        browser = "Microsoft Edge"
    elif "firefox/" in lowered:
        browser = "Firefox"
    elif "chrome/" in lowered or "chromium/" in lowered:
        browser = "Chrome"
    elif "safari/" in lowered:
        browser = "Safari"

    platform = "Unknown device"
    if "windows" in lowered:
        platform = "Windows"
    elif "android" in lowered:
        platform = "Android"
    elif "iphone" in lowered or "ipad" in lowered:
        platform = "iOS/iPadOS"
    elif "mac os" in lowered or "macintosh" in lowered:
        platform = "macOS"
    elif "linux" in lowered:
        platform = "Linux"
    return f"{browser} on {platform}"
