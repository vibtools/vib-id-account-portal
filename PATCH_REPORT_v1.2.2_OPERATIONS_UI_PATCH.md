# Vib ID Account Portal v1.2.2 — Operations UI Patch Report

## Baseline

`v1.2.1_MOBILE_LOGOUT_HOTFIX` is the baseline for this update.

## Scope

Changed only low-risk operational and footer presentation items:

- Added private operator-only monitoring script under `scripts/internal-ops/`.
- Added private monitoring documentation under `docs/`.
- Replaced the user-facing footer request-id display with VibTools copyright text.
- Kept request ID generation and `X-Request-ID` response header intact for observability.
- Updated release version metadata to `1.2.2`.

## Explicit non-goals

- No public monitoring page.
- No user-facing operations dashboard.
- No database migration.
- No authentication flow change.
- No Keycloak configuration change.
- No Keycloak restart requirement.
- No secret handling change.

## Deployment target

Redeploy only the `id.vib.tools` portal service through the normal rolling deployment path.
