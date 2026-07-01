"""Authenticated encryption for server-side secrets and token bundles."""

from __future__ import annotations

import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


class EncryptionError(ValueError):
    pass


class TokenCipher:
    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key.encode("ascii"))

    def encrypt_bytes(self, plaintext: bytes) -> bytes:
        return self._fernet.encrypt(plaintext)

    def decrypt_bytes(self, ciphertext: bytes) -> bytes:
        try:
            return self._fernet.decrypt(ciphertext)
        except InvalidToken as exc:
            raise EncryptionError("encrypted material failed authentication") from exc

    def encrypt_json(self, payload: dict[str, Any]) -> bytes:
        serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return self.encrypt_bytes(serialized)

    def decrypt_json(self, ciphertext: bytes) -> dict[str, Any]:
        try:
            value = json.loads(self.decrypt_bytes(ciphertext))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise EncryptionError("encrypted JSON payload is invalid") from exc
        if not isinstance(value, dict):
            raise EncryptionError("encrypted JSON payload must be an object")
        return value
