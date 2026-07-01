"""Account form validation and normalization."""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import phonenumbers
from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, Field, field_validator, model_validator

from app.database.models.enums import ContactType

LANGUAGE_PATTERN = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
SAFE_TEXT_PATTERN = re.compile(r"^[^\x00-\x1f\x7f]*$")
SERVICE_KEY_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


def clean_text(value: str, *, max_length: int, required: bool = False) -> str | None:
    normalized = unicodedata.normalize("NFC", value).strip()
    if not normalized:
        if required:
            raise ValueError("This field is required")
        return None
    if len(normalized) > max_length:
        raise ValueError(f"Must not exceed {max_length} characters")
    if not SAFE_TEXT_PATTERN.fullmatch(normalized):
        raise ValueError("Control characters are not allowed")
    return normalized


def validate_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("Unknown timezone") from exc
    return value


class ProfileUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    phone_number: str | None = Field(default=None, max_length=32)
    phone_country_code: str | None = Field(default=None, max_length=8)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    timezone: str = Field(max_length=64)
    preferred_language: str = Field(max_length=16)
    organization_name: str | None = Field(default=None, max_length=160)
    job_title: str | None = Field(default=None, max_length=120)
    version: datetime

    @field_validator("display_name")
    @classmethod
    def name_is_safe(cls, value: str) -> str:
        return str(clean_text(value, max_length=120, required=True))

    @field_validator("organization_name")
    @classmethod
    def organization_is_safe(cls, value: str | None) -> str | None:
        return clean_text(value or "", max_length=160)

    @field_validator("job_title")
    @classmethod
    def job_title_is_safe(cls, value: str | None) -> str | None:
        return clean_text(value or "", max_length=120)

    @field_validator("country_code")
    @classmethod
    def country_is_valid(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        result = value.strip().upper()
        if not result.isalpha() or len(result) != 2:
            raise ValueError("Country code must contain two letters")
        return result

    @field_validator("preferred_language")
    @classmethod
    def language_is_valid(cls, value: str) -> str:
        value = value.strip()
        if not LANGUAGE_PATTERN.fullmatch(value):
            raise ValueError("Language must be a valid BCP 47-style code")
        return value

    @field_validator("timezone")
    @classmethod
    def timezone_is_valid(cls, value: str) -> str:
        return validate_timezone(value)

    @model_validator(mode="after")
    def normalize_phone(self) -> ProfileUpdate:
        raw = (self.phone_number or "").strip()
        country = (self.phone_country_code or "").strip()
        if not raw:
            self.phone_number = None
            self.phone_country_code = None
            return self
        candidate = raw if raw.startswith("+") else f"{country}{raw}"
        try:
            parsed = phonenumbers.parse(candidate, None)
        except phonenumbers.NumberParseException as exc:
            raise ValueError("Phone number is invalid") from exc
        if not phonenumbers.is_valid_number(parsed):
            raise ValueError("Phone number is invalid")
        self.phone_number = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        self.phone_country_code = f"+{parsed.country_code}"
        return self


class ContactCreate(BaseModel):
    contact_type: ContactType
    label: str = Field(min_length=1, max_length=40)
    value: str = Field(min_length=1, max_length=255)
    is_primary: bool = False

    @field_validator("label")
    @classmethod
    def label_is_safe(cls, value: str) -> str:
        return str(clean_text(value, max_length=40, required=True))

    @field_validator("value")
    @classmethod
    def value_is_safe(cls, value: str) -> str:
        return str(clean_text(value, max_length=255, required=True))

    def normalized(self) -> str:
        if self.contact_type == ContactType.EMAIL:
            try:
                validated = validate_email(self.value, check_deliverability=False)
            except EmailNotValidError as exc:
                raise ValueError("Email contact is invalid") from exc
            return validated.normalized.casefold()
        if self.contact_type == ContactType.PHONE:
            try:
                parsed = phonenumbers.parse(self.value, None)
            except phonenumbers.NumberParseException as exc:
                raise ValueError("Phone contact must use international format") from exc
            if not phonenumbers.is_valid_number(parsed):
                raise ValueError("Phone contact is invalid")
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        return self.value.casefold()


class ServiceTouchPayload(BaseModel):
    subject: str = Field(min_length=3, max_length=255)
    service_key: str = Field(min_length=1, max_length=64)
    authenticated_at: datetime

    @field_validator("subject")
    @classmethod
    def subject_is_safe(cls, value: str) -> str:
        return str(clean_text(value, max_length=255, required=True))

    @field_validator("service_key")
    @classmethod
    def service_key_is_valid(cls, value: str) -> str:
        if not SERVICE_KEY_PATTERN.fullmatch(value):
            raise ValueError("service_key format is invalid")
        return value

    @field_validator("authenticated_at")
    @classmethod
    def timestamp_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("authenticated_at must include a timezone")
        normalized = value.astimezone(UTC)
        if normalized > datetime.now(UTC) + timedelta(minutes=5):
            raise ValueError("authenticated_at cannot be more than five minutes in the future")
        return normalized
