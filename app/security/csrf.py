"""Session-bound CSRF token generation and verification."""

from __future__ import annotations

import base64
import hashlib
import hmac


class CSRFProtector:
    def __init__(self, secret: str) -> None:
        self._secret = secret.encode("utf-8")

    def token_for_session(self, raw_session_id: str) -> str:
        digest = hmac.new(self._secret, raw_session_id.encode("utf-8"), hashlib.sha256).digest()
        return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")

    def validate(self, raw_session_id: str, supplied: str | None) -> bool:
        if not supplied:
            return False
        expected = self.token_for_session(raw_session_id)
        return hmac.compare_digest(expected, supplied)
