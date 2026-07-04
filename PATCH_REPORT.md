# Vib ID Account Portal v1.2.0 — Patch Report

This release supersedes v1.1.0 and introduces the native `id.vib.tools` account-security module.

## Added

- `app/account_security/` module
- Native security pages for password, email, 2FA, recovery codes, sessions, and applications
- JSON account/security/application APIs
- Keycloak management methods for required actions, verification, sessions, credentials, and consents
- Tests for native security pages, action flows, APIs, Keycloak adapter methods, failure behavior, and defensive service branches
- `docs/ACCOUNT_SECURITY_MODULE.md`

## Changed

- Updated application version from `1.1.0` to `1.2.0`
- Updated primary navigation to use `/security/sessions` and `/applications`
- Updated account menu and command palette to use native `/security`
- Updated profile and sessions page actions to avoid Keycloak Account Console links
- Updated `/security` overview to become the native Security Module hub
- Updated release script archive name to `Vib_ID_Account_Portal_v1.2.0_SECURITY_MODULE.zip`

## Unchanged

- OIDC login/callback/logout behavior
- Keycloak authentication theme
- Database schema and Alembic head
- Existing `/profile`, `/sessions`, `/services`, `/activity`, `/preferences`, health, and internal service APIs
- Existing Docker/Coolify topology
- Production dependencies

## Security repairs

- Removed user-facing reliance on the Keycloak Account Console
- Kept password and 2FA setup inside Keycloak required-action flows
- Added explicit CSRF and rate-limit enforcement around new sensitive routes
- Added audit logging for password/email/MFA/session/application actions
- Kept tokens and secrets server-side only
