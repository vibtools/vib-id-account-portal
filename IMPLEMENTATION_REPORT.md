# Vib ID Account Portal — Implementation Report

**Version:** 1.0.1
**Implementation date:** 2026-07-01
**Target:** `https://id.vib.tools`
**Identity authority:** `https://auth.vib.tools/realms/vib`

## 1. Architecture implemented

The project implements a modular, server-rendered FastAPI account portal with an asynchronous SQLAlchemy 2 data layer and PostgreSQL as the production database. The portal is deliberately separated from the identity authority: Keycloak remains the sole owner of credentials, primary email state, TOTP, recovery flows, central sessions, and token issuance.

The application boundary is divided into:

- OIDC authentication and callback handling.
- Encrypted server-side session management.
- Account profile and contact management.
- Security status and Keycloak account-management links.
- Portal-session listing and revocation.
- Read-only connected-service history.
- User-scoped activity history.
- User preferences.
- Internal service-connection recording.
- Health, operational CLI, retention cleanup, and deployment tooling.

The runtime uses one Uvicorn worker by default and is structured so additional replicas can share session and rate-limit state through PostgreSQL.

## 2. Authentication and session implementation

The interactive client implements OpenID Connect Authorization Code Flow with PKCE S256. Login transactions include cryptographically random state, nonce, and code verifier values. Callback processing enforces transaction expiry, one-time consumption, exact redirect configuration, issuer, signature, audience, authorized-party, expiration, not-before, nonce, and subject validation.

The browser receives only an opaque random cookie identifier. The corresponding session record stores:

- A SHA-256 hash of the opaque identifier.
- The immutable OIDC `sub` subject.
- An authenticated-encryption token bundle.
- Privacy-preserving network identifier.
- User-agent and device summary.
- Creation, last-seen, idle-expiry, absolute-expiry, and revocation fields.
- Optional Keycloak session identifier for back-channel logout.

Session identifiers rotate after authentication. Raw session IDs and OIDC tokens are not written to application logs or browser storage. Logout revokes local material and uses the OIDC end-session endpoint when available. Back-channel logout validates signed logout tokens and rejects replayed token identifiers.

## 3. Database implementation

The initial Alembic migration creates the required production schema, constraints, partial uniqueness rules, indexes, and timestamps for:

- `user_profiles`
- `user_contacts`
- `portal_sessions`
- `service_registry`
- `user_service_connections`
- `security_activity`
- `user_preferences`
- OIDC login transactions
- Back-channel logout replay records
- Shared database rate-limit buckets

Every user-owned record is keyed by the validated OIDC `sub`; email is never used as an immutable relation key. Contact constraints prevent duplicate primary contacts of the same type. Service connections are unique per subject and service.

## 4. Functional modules

### Overview

Provides greeting, profile completeness, primary email and verification state, 2FA and central-account status when available, active-session information, connected-service count, recent activity, security recommendations, and direct navigation to core account areas.

### Profile and contacts

Supports validated updates for display name, phone, country, timezone, language, organization, job title, and bounded additional contacts. Inputs have length, enum, Unicode/control-character, duplicate, and normalization controls. Optimistic version checks protect against accidental concurrent overwrites. Primary email remains read-only and routes to the central Vib ID account flow for changes.

### Security

Shows email-verification status, 2FA status, central account state, local session security, and recent important activity. Password, email, two-factor, and recovery management are handled only through branded Keycloak account-management URLs.

### Sessions

Lists current and other portal sessions with device summary, privacy-preserving network representation, creation, activity, and expiry information. Users can revoke another local session, revoke all other local sessions, terminate the current session, and invoke approved central logout. Target subjects are always derived server-side from the authenticated session.

### Connected services

Shows a read-only list of registered Vib-owned services, first connection, last authentication, and status. The interface does not expose client IDs, redirect URIs, scopes, tokens, secrets, disconnect controls, or service-management functions.

### Activity

Provides subject-isolated, paginated activity records with bounded date filters and allowlisted, redacted metadata.

### Preferences

Persists system/light/dark theme, locale, timezone, and security-notification preference. Product announcements default to disabled.

## 5. Internal service tracking

`POST /internal/v1/service-connections/touch` accepts only validated Keycloak client-credentials tokens. Validation includes signature, issuer, audience, expiration, authorized party/client ID, required role, and service-client binding.

An allowlisted backend can record activity only for its matching service key. Approved clients must use either the exact service key or the `${service_key}-backend` naming convention. End-user tokens, cross-service attempts, unknown service keys, oversized payloads, missing roles, forged tokens, and rate-limit violations are rejected with generic responses.

Service metadata is managed only through CLI commands for register/update, list, and deactivate operations. No browser administration interface exists.

## 6. Security controls

Implemented controls include:

- Session-bound synchronizer CSRF tokens and constant-time comparison.
- POST-only browser state changes.
- Strict trusted-host validation.
- Production HTTPS and secure-cookie fail-closed validation.
- Content Security Policy with local assets and per-request nonces.
- HSTS, frame denial, MIME-sniffing prevention, strict referrer policy, permissions policy, and authenticated-page no-store headers.
- Asynchronous database-backed rate limiting suitable for multiple application replicas.
- Request body limits.
- Global safe exception handling and correlation IDs.
- Structured logging with authorization, cookie, token, secret, password, and database URL redaction.
- Jinja autoescaping and no unsafe rendering of user-controlled content.
- Parameterized SQLAlchemy operations.
- No arbitrary outbound URL proxy or user-controlled SSRF surface.
- Privacy-preserving IP representation using a keyed digest.
- Configurable activity/session retention and cleanup CLI.
- Keycloak management token held in memory only, with timeout, retry, and circuit-breaker behavior.

## 7. UI and accessibility

The UI is mobile-first and server rendered. It includes desktop navigation, compact mobile navigation, local CSS, local SVG icons, system/light/dark themes, visible focus states, semantic landmarks, associated labels, accessible validation feedback, reduced-motion support, touch-sized controls, non-color-only statuses, and core operation without JavaScript.

JavaScript is limited to progressive enhancement for mobile navigation, theme preview, filter submission, and destructive-action confirmation. No external CDN, analytics, tracker, font runtime, or frontend framework is used.

## 8. Deployment implementation

The project includes:

- Multi-stage Dockerfile.
- Dedicated production builder, isolated test stage, and non-root runtime stage.
- Hashed dependency requirements.
- Read-only-root-filesystem-compatible runtime design with writable temporary storage.
- Container health check on port 8000.
- Separate migration service in Compose.
- PostgreSQL-only private networking.
- Migration-first PostgreSQL test Compose environment.
- Complete Coolify deployment, Keycloak setup, operations, backup/restore, incident response, and service-integration documentation.
- Secret generation, database wait, template validation, load-test, release-integrity, audit, and deterministic release scripts.

## 9. Important design decisions

1. Keycloak is never duplicated inside the portal.
2. The OIDC subject is the only immutable identity key.
3. Sensitive account changes redirect to the identity authority instead of expanding portal privilege.
4. Portal sessions and rate limits use PostgreSQL so process-local memory is not a security dependency.
5. Connected services are reference-only to users and CLI-managed operationally.
6. Keycloak management access is restricted to explicit operations and self-derived targets.
7. The production container excludes Node.js, tests, development tools, and secrets.
8. The separate Docker test target contains development dependencies and runs Alembic before PostgreSQL tests.

## 10. Delivered source state

The source tree contains complete application modules, templates, local static assets, schema migration, test suites, operational scripts, pinned dependencies, Docker/Compose definitions, and deployment documentation. There are no source-level unfinished implementation markers or embedded production credentials.
