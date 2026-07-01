"""Database enums."""

from enum import StrEnum


class ContactType(StrEnum):
    EMAIL = "email"
    PHONE = "phone"
    WEBSITE = "website"
    OTHER = "other"


class Theme(StrEnum):
    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


class ActivitySeverity(StrEnum):
    INFO = "info"
    NOTICE = "notice"
    WARNING = "warning"
    CRITICAL = "critical"


class ActivityResult(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


class ConnectionStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
