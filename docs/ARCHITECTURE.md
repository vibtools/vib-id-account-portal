# Architecture

## Trust boundaries

1. **Browser boundary:** receives only the `__Host-vib_id_session` opaque cookie. No OIDC token is exposed to browser storage or templates.
2. **Portal boundary:** FastAPI validates requests, CSRF, session state, and subject isolation. Sensitive token bundles are decrypted only in application memory.
3. **Identity boundary:** `auth.vib.tools/realms/vib` is the sole authority for credentials and central authentication.
4. **Database boundary:** portal PostgreSQL stores portal-owned data, hashed session identifiers, encrypted token bundles, audit events, rate-limit buckets, and service-reference metadata.
5. **Internal service boundary:** approved SaaS backends call one non-browser endpoint with a Keycloak client-credentials token.

## Modules

- `app/auth`: OIDC flow, JWT validation, sessions, back-channel logout, Keycloak management.
- `app/accounts`: profile/contact schemas, persistence, and browser pages.
- `app/services_registry`: read-only user list, internal touch endpoint, operational registry commands.
- `app/activity`: subject-isolated paginated audit history.
- `app/preferences`: appearance, locale, timezone, and security-notification choices.
- `app/middleware`: request IDs, body limits, security headers, and database-backed rate limiting.
- `app/security`: encryption, CSRF, privacy identifiers, and audit redaction.

## Request lifecycle

The request ID middleware assigns a validated correlation ID. Trusted-host and payload-size checks run before route parsing. Authentication resolves the hashed cookie against an active, non-expired database session. Preferences are loaded for server-side theme and timezone rendering. State-changing routes validate the session-bound CSRF token, enforce a database-backed rate limit, apply a subject-scoped mutation, record a redacted audit event, and commit atomically.

## OIDC lifecycle

Login creates random state, nonce, and PKCE verifier values. The state is stored only as a hash; the verifier is encrypted. The callback consumes the transaction once, exchanges the code with the exact redirect URI and verifier, validates the signed ID token, rotates any prior portal session, and stores the new encrypted token bundle. Logout revokes local state and uses the provider end-session endpoint when available.

## Failure behavior

Keycloak management failures are isolated behind short timeouts and a circuit breaker. Dashboard and security pages show unavailable status without exposing provider details. Database or OIDC discovery failure marks readiness as unavailable. Production exceptions return generic messages with request IDs.
