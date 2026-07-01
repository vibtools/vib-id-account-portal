from __future__ import annotations

import base64

import pytest

from app.security.audit import redact_metadata
from app.security.csrf import CSRFProtector
from app.security.encryption import EncryptionError, TokenCipher
from app.security.identifiers import (
    device_label,
    generate_opaque_token,
    privacy_ip,
    sanitize_user_agent,
    sha256_text,
)


def test_token_cipher_round_trip_and_tamper_detection() -> None:
    cipher = TokenCipher("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
    ciphertext = cipher.encrypt_json({"refresh_token": "private", "count": 2})
    assert b"private" not in ciphertext
    assert cipher.decrypt_json(ciphertext) == {"count": 2, "refresh_token": "private"}
    tampered = bytearray(ciphertext)
    tampered[-1] ^= 1
    with pytest.raises(EncryptionError):
        cipher.decrypt_json(bytes(tampered))
    invalid_json = cipher.encrypt_bytes(b"[]")
    with pytest.raises(EncryptionError):
        cipher.decrypt_json(invalid_json)


def test_identifiers_are_safe_and_stable() -> None:
    token = generate_opaque_token()
    assert len(base64.urlsafe_b64decode(token + "==")) >= 32
    assert sha256_text("value") == sha256_text("value")
    assert privacy_ip("192.0.2.1", "k" * 32) == privacy_ip("192.0.2.1", "k" * 32)
    assert privacy_ip("bad-ip", "k" * 32) == privacy_ip(None, "k" * 32)
    assert sanitize_user_agent(" Chrome\x00\n ") == "Chrome"
    assert device_label("Mozilla Chrome/149 Windows") == "Chrome on Windows"
    assert device_label("Firefox/1 Android") == "Firefox on Android"
    with pytest.raises(ValueError):
        generate_opaque_token(10)


def test_csrf_is_bound_to_session_and_constant_shape() -> None:
    protector = CSRFProtector("s" * 32)
    token = protector.token_for_session("session-a")
    assert protector.validate("session-a", token)
    assert not protector.validate("session-b", token)
    assert not protector.validate("session-a", None)


def test_audit_metadata_allowlist_redacts_sensitive_and_bounds_values() -> None:
    redacted = redact_metadata(
        {
            "service_key": "ygit-net",
            "status": "x" * 400,
            "password": "never",
            "access_token": "never",
            "field_names": list(range(30)),
            "unknown": "drop",
        }
    )
    assert redacted["service_key"] == "ygit-net"
    assert len(str(redacted["status"])) == 256
    assert len(redacted["field_names"]) == 20
    assert "password" not in redacted
    assert "access_token" not in redacted
    assert redact_metadata(None) == {}


def test_advisory_lock_key_is_stable_signed_64_bit() -> None:
    from app.database.locks import advisory_lock_key

    first = advisory_lock_key("rate-limit", "identity")
    assert first == advisory_lock_key("rate-limit", "identity")
    assert first != advisory_lock_key("service-connection", "identity")
    assert -(2**63) <= first < 2**63
