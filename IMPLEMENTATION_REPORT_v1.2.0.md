# Vib ID Account Portal v1.2.0 — Implementation Report

**Release date:** 2026-07-04  
**Baseline:** Vib ID Account Portal v1.1.0 production source  
**Scope:** Native Vib ID Security Module replacing user-facing Keycloak Account Console dependency

## Project analysis

The v1.1.0 source already provided a secure FastAPI/Jinja2 portal, OIDC Authorization Code Flow with PKCE S256, encrypted server-side token storage, hashed opaque sessions, CSRF protection, rate limiting, security activity logs, Keycloak management-client health/status calls, local session management, and a read-only connected-service registry. The v1.2.0 update treats those elements as compatibility boundaries and adds a native account-security module without changing the database schema.

## Architecture preserved

- FastAPI application factory and route topology
- Jinja2 server-rendered templates
- PostgreSQL/Alembic topology; no new migration required
- Keycloak as the sole credential, email-verification, password, TOTP, token, and global-session authority
- OIDC Authorization Code Flow with PKCE S256
- Encrypted server-side token bundles and secure opaque session cookies
- CSRF protection on state-changing browser routes
- Subject-scoped data access
- Existing Docker, Compose, and Coolify deployment model

## Implementation summary

### New module

Added `app/account_security/`:

- `routes.py` — native pages and JSON APIs
- `service.py` — safe presentation mappers and central-session helpers
- `schemas.py` — response models for profile, security status, sessions, and applications

### New pages

- `/security/password`
- `/security/email`
- `/security/2fa`
- `/security/recovery-codes`
- `/security/sessions`
- `/applications`

### New API endpoints

- `GET /api/account/profile`
- `GET /api/security/status`
- `GET /api/security/2fa/status`
- `GET /api/security/sessions`
- `GET /api/applications`
- `DELETE /api/applications/{client_id}/consent`

### Keycloak management-client expansion

Added bounded methods for required-action emails, email verification, email update, central sessions, credentials, TOTP credential removal, consents, and consent revocation.

### Navigation replacement

Removed user-facing Keycloak Account Console links from the account menu, command palette, profile page action, sessions page action, and primary navigation. Account/security routes now resolve inside `id.vib.tools`.

## Security controls added

- Sensitive actions require authenticated sessions
- POST/PATCH/DELETE-like mutations require CSRF
- Consent revocation API requires `X-CSRF-Token`
- Password/email/2FA/session/application actions are rate limited
- Sensitive actions are audit logged
- Portal never renders raw access tokens, refresh tokens, ID tokens, client secrets, passwords, TOTP seeds, or recovery codes
- Recovery-code page is intentionally disabled until Keycloak capability is verified

## Database impact

No schema change. No Alembic migration required.
