# Vib ID Native Account Security Module v1.2.0

## Purpose

The v1.2.0 security module replaces the user-facing dependency on the Keycloak Account Console with native `id.vib.tools` pages while preserving Keycloak as the sole identity, credential, email verification, TOTP, token, and global-session authority.

## Pages

- `/security` — overview and security-module action hub
- `/security/password` — sends Keycloak `UPDATE_PASSWORD` required-action email
- `/security/email` — shows email status, resends verification, and requests primary-email change
- `/security/2fa` — sends Keycloak `CONFIGURE_TOTP` required-action email and supports protected TOTP credential removal
- `/security/recovery-codes` — safe disabled state until Keycloak recovery-code capability is verified
- `/security/sessions` — native portal sessions plus central Keycloak session visibility where available
- `/applications` — connected application and service history

## API endpoints

- `GET /api/account/profile`
- `GET /api/security/status`
- `GET /api/security/2fa/status`
- `GET /api/security/sessions`
- `GET /api/applications`
- `DELETE /api/applications/{client_id}/consent`

## Security controls

- Authenticated portal session required for all module routes
- CSRF required for all browser mutation forms
- `X-CSRF-Token` required for consent revocation API
- Rate limiting on password, email, 2FA, session, and application revocation actions
- Audit logging for sensitive actions
- No raw token, password, client secret, TOTP seed, or recovery code exposure to browser templates
- No direct Keycloak database writes
- No Keycloak Account Console CSS or PatternFly overrides

## Keycloak management methods added

- `get_user`
- `update_user_email`
- `send_verify_email`
- `execute_required_actions_email`
- `list_user_sessions`
- `list_user_credentials`
- `remove_totp_credentials`
- `list_user_consents`
- `revoke_user_consent`

## Design boundary

All UI follows the existing v1.1.0 Vib ID portal shell, topbar, sidebar, dense cards, local assets, and dark/light/system theme. `auth.vib.tools` remains responsible for login, registration, required actions, verification links, and token issuance. `id.vib.tools` is responsible for user-facing account and security management.
