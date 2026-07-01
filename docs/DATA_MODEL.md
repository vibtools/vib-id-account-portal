# Data Model

## Identity key

`subject` is the immutable OIDC `sub` value. Email is display data from Keycloak and is never used as an identity key.

## Tables

- `user_profiles`: extended profile and contact summary fields.
- `user_contacts`: bounded additional contacts with duplicate and one-primary-per-type constraints.
- `user_preferences`: system/light/dark theme, locale, timezone, and notification choices.
- `portal_sessions`: hashed opaque identifier, encrypted token bundle, privacy-preserving network reference, device summary, timeouts, and revocation state.
- `oidc_transactions`: one-time hashed state, encrypted PKCE verifier, nonce, expiry, and consumption marker.
- `logout_token_replays`: hashed back-channel logout `jti` values until token expiry.
- `service_registry`: CLI-managed approved service metadata.
- `user_service_connections`: unique subject/service connection history.
- `security_activity`: subject-isolated structured activity with redacted metadata.
- `rate_limit_buckets`: cross-instance fixed-window enforcement.
- `migration_locks`: reserved operational coordination table.

## Retention defaults

Security activity is retained for 180 days. Revoked sessions are retained for 30 days. Expired OIDC transactions, logout replay records, and rate-limit buckets are removed by `vib-id cleanup`. Values are configurable within bounded ranges.

## Time handling

All stored timestamps are timezone-aware UTC. Rendering uses the user-selected timezone with UTC fallback.
