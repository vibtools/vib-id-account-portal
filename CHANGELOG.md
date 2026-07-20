# Changelog

## 1.3.0 — 2026-07-20

- Added Account Experience profile photo upload/remove with strict PNG/JPEG/WebP validation and size limits.
- Added portable profile API for current user and internal connected-service consumers.
- Added social/profile link management with safe URL validation and app/private visibility.
- Improved Applications page to include YGIT/YGIT Dev from central Keycloak sessions when service touch data is not yet present.
- Added additive database migration for profile photos and social links.
- Preserved existing auth, security module, session, OIDC, email, and monitoring behavior.

## 1.2.2 — 2026-07-05

- Added private operator-only operations monitoring script under `scripts/internal-ops/`.
- Replaced the normal portal footer request-id display with VibTools copyright text.
- Preserved request ID generation, server logging, and `X-Request-ID` response headers.
- Added no user-facing monitoring page, route, or navigation item.
- Requires no database migration and no Keycloak restart.

## 1.2.0 — 2026-07-04

- Added the native Vib ID Security Module on top of the v1.1.0 portal baseline.
- Added `/security/password`, `/security/email`, `/security/2fa`, `/security/recovery-codes`, `/security/sessions`, and `/applications` pages.
- Replaced user-facing Keycloak Account Console links in the account menu, command palette, profile action, sessions action, and primary navigation.
- Added Keycloak management-client support for required-action emails, verify-email requests, email updates, credential listing/removal, central sessions, and consent revocation.
- Added JSON APIs for account profile summary, security status, 2FA status, sessions, and applications.
- Added CSRF, rate-limit, audit-log, and no-token-exposure protections for new sensitive actions.
- Kept Keycloak as the sole credential, password, email-verification, and TOTP authority.
- Kept database schema unchanged; no Alembic migration is required for v1.2.0.
- Expanded tests from 52 to 56 with 90.35% branch-aware coverage.

## 1.1.0 — 2026-07-03

- Rebuilt the authenticated portal shell around the Vib Tools Open Source Hub design system.
- Added the official Vib Tools blue/cyan, dark/light, typography, border, spacing, and component tokens.
- Replaced the heavy dashboard styling with flat, high-density cards, panels, tables, forms, and status indicators.
- Added a keyboard-first command palette available with Ctrl/Cmd+K or `/`.
- Added a global quick-theme control that preserves locale, timezone, and notification preferences.
- Added a compact GitHub/Linear-inspired top bar, responsive navigation drawer, account menu, and mobile-safe layouts.
- Added explicit dark/light brand asset slots with replacement documentation.
- Preserved all existing profile, contact, security, session, service, activity, preference, OIDC, CSRF, and audit behavior.
- Expanded UI regression coverage for navigation, command search, quick theme updates, and responsive rendering.

## 1.0.1 — 2026-07-01

- Fixed Keycloak service-account token identification to validate `preferred_username` while retaining UUID `sub` claims.
- Fixed Docker health checks under strict trusted-host validation.
- Removed the host port 8000 collision from the production Compose definition.
- Added fresh central email-verification status with token-claim fallback.
- Added OIDC discovery endpoint origin validation and disabled ambient HTTP proxy inheritance.
- Added graceful local logout and callback behavior during identity-provider network faults.
- Added invalid management-response handling and static-asset versioning.
- Added PostgreSQL advisory-lock protection for rate-limit, account-bootstrap, and service-connection first-write races.
- Corrected profile optimistic locking to use row locking and full timestamp precision.
- Added standards-aware contact email validation and normalized storage.
- Rejected internal service timestamps more than five minutes in the future.


## 1.0.0 — 2026-06-30

- Added FastAPI/Jinja2 Vib ID account portal.
- Added OIDC Authorization Code Flow with PKCE S256, state, nonce, issuer, audience, authorized-party, and JWKS validation.
- Added encrypted server-side token storage and hashed opaque session cookies.
- Added profile/contact, security, sessions, connected services, activity, and preferences modules.
- Added Keycloak back-channel logout and least-privilege management client integration.
- Added internal client-credentials protected service-connection tracking.
- Added PostgreSQL schema and Alembic migration.
- Added responsive light/dark/system UI and local assets.
- Added Docker, Compose, Coolify, operations, backup, incident, and service-integration documentation.
- Added automated unit, integration, security, and browser test suites.
