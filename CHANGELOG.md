# Changelog

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
