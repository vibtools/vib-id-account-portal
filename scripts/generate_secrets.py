#!/usr/bin/env python3
"""Generate independent application secrets without writing them to disk."""

from __future__ import annotations

import secrets

from cryptography.fernet import Fernet


def main() -> None:
    print(f"APP_SECRET_KEY={secrets.token_urlsafe(48)}")
    print(f"TOKEN_ENCRYPTION_KEY={Fernet.generate_key().decode('ascii')}")
    print(f"CSRF_SECRET={secrets.token_urlsafe(48)}")
    print(f"IP_PRIVACY_KEY={secrets.token_urlsafe(48)}")


if __name__ == "__main__":
    main()
