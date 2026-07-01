# Security Controls

## Authentication and sessions

- Authorization Code Flow only; no direct-access/password flow.
- PKCE S256, state, nonce, signature, issuer, audience, `azp`, expiration, and not-before checks.
- Discovery issuer must exactly match the configured issuer.
- Browser cookie is `Secure`, `HttpOnly`, `SameSite=Lax`, host-only, path `/`, and bounded by the absolute session lifetime.
- Database stores only a SHA-256 session hash.
- Token bundles use authenticated encryption with an environment-provided key.
- Session rotation occurs after authentication.
- Idle, absolute, concurrent-session, revocation, and back-channel logout controls are enforced.

## Browser controls

- Synchronizer-style CSRF token is HMAC-bound to the current opaque session.
- CSP permits only local scripts/styles/assets and the locked authentication origin.
- Framing, object embedding, mixed content, MIME sniffing, sensitive-page caching, referrer leakage, and unnecessary browser capabilities are restricted.
- Jinja autoescape is enabled; untrusted `safe` rendering is prohibited by release checks.
- No third-party analytics, fonts, icons, scripts, or advertising trackers are present.

## Authorization

Every user query derives `subject` from the validated server-side session. Browser requests never supply a target user identifier. Session and contact mutations include the authenticated subject in the database predicate. Connected services are read-only for users.

## Internal endpoint

`POST /internal/v1/service-connections/touch` validates signature, issuer, audience, expiry, authorized party, service-account subject, allowlisted client ID, and required role. End-user tokens and unknown services are rejected with generic responses. CORS is not enabled.

## Secrets and logging

Production starts only with non-default secrets and HTTPS public URLs. Logs never include cookies, authorization headers, passwords, token values, database URLs, or provider secrets. Audit metadata uses a strict key allowlist and size cap.

## Key rotation

Rotate client secrets in Keycloak and Coolify secret storage. Token-encryption key rotation requires a controlled dual-key migration: deploy read-old/write-new support, re-encrypt active rows, verify counts, then remove the old key. Rotate CSRF and privacy keys during a maintenance window because existing CSRF tokens or IP references will change.
