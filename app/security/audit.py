"""Security activity creation with metadata allowlisting and redaction."""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.enums import ActivityResult, ActivitySeverity
from app.database.models.security import SecurityActivity

ALLOWED_METADATA_KEYS = {
    "field_names",
    "service_key",
    "target_session",
    "reason",
    "client_id",
    "status",
    "page",
}
SENSITIVE_FRAGMENTS = {"token", "secret", "password", "authorization", "cookie", "code_verifier"}


def redact_metadata(metadata: Mapping[str, object] | None) -> dict[str, object]:
    if not metadata:
        return {}
    result: dict[str, object] = {}
    for key, value in metadata.items():
        normalized = str(key).lower()
        if key not in ALLOWED_METADATA_KEYS or any(
            part in normalized for part in SENSITIVE_FRAGMENTS
        ):
            continue
        if isinstance(value, str):
            result[key] = value[:256]
        elif isinstance(value, (bool, int, float)) or value is None:
            result[key] = value
        elif isinstance(value, list):
            result[key] = [str(item)[:80] for item in value[:20]]
    encoded_size = len(str(result).encode("utf-8"))
    if encoded_size > 2048:
        return {"status": "metadata-truncated"}
    return result


async def record_activity(
    db: AsyncSession,
    *,
    subject: str | None,
    event_type: str,
    request_id: str,
    ip_privacy_value: str,
    user_agent_summary: str,
    result: ActivityResult = ActivityResult.SUCCESS,
    severity: ActivitySeverity = ActivitySeverity.INFO,
    metadata: Mapping[str, object] | None = None,
) -> SecurityActivity:
    activity = SecurityActivity(
        subject=subject,
        event_type=event_type[:80],
        event_severity=severity,
        result=result,
        request_correlation_id=request_id[:64],
        ip_privacy_value=ip_privacy_value,
        user_agent_summary=user_agent_summary[:255],
        event_metadata=redact_metadata(metadata),
    )
    db.add(activity)
    await db.flush()
    return activity
