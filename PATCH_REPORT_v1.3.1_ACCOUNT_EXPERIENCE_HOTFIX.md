# Patch Report — Vib ID Account Portal v1.3.1 Account Experience Hotfix

## Baseline

- Baseline package: `Vib_ID_Account_Portal_v1.3.0_ACCOUNT_EXPERIENCE`
- Baseline SHA-256 verified: `615469e71954074900589483b7cb94f194986913d984b6ffa9a9930182bc614f`
- Target version: `1.3.1`

## Required Updates Implemented

### Update 1 — Applications Page

- Added first-class VibTools app catalog rendering for YGIT and YGIT Dev.
- Preserved service-history behavior and API behavior for actual service connections.
- Added robust central-session client alias detection for frontend/backend names including:
  - `ygit`
  - `ygit-net`
  - `ygit-backend`
  - `ygit-net-backend`
  - `ygit-dev`
  - `ygit-dev-backend`
  - `service-account-*` variants
- Applications page now has separate sections:
  - Available VibTools apps
  - Connected applications / service history

### Update 2 — Profile Page API Button + Account Data Download

- Removed normal-user `Preview portable profile API` button from Profile & Contacts.
- Removed user-facing profile-page wording that exposed API implementation details.
- Preserved backend endpoints:
  - `GET /api/account/profile/portable`
  - `GET /internal/v1/account-profiles/{subject}`
- Added Preferences → Privacy & data export actions:
  - `GET /preferences/account-data.txt`
  - `GET /preferences/account-data.csv`
- Account data export is authenticated, rate-limited, audit-logged, and uses attachment responses with `no-store` cache headers.
- Export excludes passwords, tokens, session cookies, service-account secrets, CSRF secrets, and raw Keycloak credential material.

### Update 3 — Default Theme

- Changed new account preference default theme from `system` to `dark`.
- Changed fallback rendering from `system` to `dark`.
- Preserved existing user-selected light/system/dark preferences.

## Database / Migration

- No Alembic migration added.
- No schema change required.
- Existing v1.3.0 migration remains unchanged.

## Keycloak / Auth

- No Keycloak realm change.
- No Keycloak theme change.
- No auth-domain redeploy required.
- Existing OIDC, session, CSRF, back-channel logout, and service-token behavior preserved.

## Files Modified

- `CHANGELOG.md`
- `app/__init__.py`
- `app/account_security/routes.py`
- `app/account_security/schemas.py`
- `app/account_security/service.py`
- `app/accounts/repository.py`
- `app/database/models/account.py`
- `app/dependencies.py`
- `app/preferences/routes.py`
- `app/services_registry/repository.py`
- `app/static/css/app.css`
- `app/templates/applications/index.html`
- `app/templates/layouts/base.html`
- `app/templates/preferences/index.html`
- `app/templates/profile/index.html`
- `docs/ACCOUNT_EXPERIENCE_V1.3.1_HOTFIX.md`
- `docs/SERVICE_INTEGRATION.md`
- `tests/integration/test_account_experience_v130.py`
- `tests/integration/test_routes.py`
- `tests/unit/test_account_experience_helpers.py`

## Files Not Modified

- No `.env`
- No `coverage.xml`
- No `app/static/brand/*.png`
- No Alembic migration files
- No Keycloak/auth theme files
