"""Profile avatar validation and content-addressing helpers."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass

from fastapi import UploadFile

ALLOWED_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/webp": (b"RIFF",),
}
EXTENSIONS = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


class AvatarValidationError(ValueError):
    """Raised when an uploaded profile image violates policy."""


@dataclass(frozen=True, slots=True)
class AvatarPayload:
    avatar_key: str
    mime_type: str
    size_bytes: int
    sha256_hash: str
    image_bytes: bytes


async def read_avatar_upload(
    upload: UploadFile,
    *,
    max_bytes: int,
    allowed_types: set[str],
) -> AvatarPayload:
    declared_type = (upload.content_type or "").split(";", 1)[0].strip().lower()
    if declared_type not in allowed_types:
        raise AvatarValidationError("Profile photo must be PNG, JPEG, or WebP.")
    data = await upload.read(max_bytes + 1)
    if not data:
        raise AvatarValidationError("Profile photo file is empty.")
    if len(data) > max_bytes:
        raise AvatarValidationError("Profile photo is larger than the configured limit.")
    detected_type = detect_mime_type(data)
    if detected_type != declared_type or detected_type not in allowed_types:
        raise AvatarValidationError("Profile photo content does not match the declared image type.")
    digest = hashlib.sha256(data).hexdigest()
    avatar_key = f"{secrets.token_urlsafe(12)}-{digest[:24]}.{EXTENSIONS[detected_type]}"
    return AvatarPayload(
        avatar_key=avatar_key,
        mime_type=detected_type,
        size_bytes=len(data),
        sha256_hash=digest,
        image_bytes=data,
    )


def detect_mime_type(data: bytes) -> str:
    if data.startswith(ALLOWED_SIGNATURES["image/png"][0]):
        return "image/png"
    if data.startswith(ALLOWED_SIGNATURES["image/jpeg"][0]):
        return "image/jpeg"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    raise AvatarValidationError("Profile photo format is not supported.")
