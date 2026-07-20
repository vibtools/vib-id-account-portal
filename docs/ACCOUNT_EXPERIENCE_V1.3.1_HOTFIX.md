# Vib ID Account Experience v1.3.1 Hotfix

## Scope

`v1.3.1_ACCOUNT_EXPERIENCE_HOTFIX` uses v1.3.0 as the baseline and applies a focused user-experience and integration hotfix.

## Changes

- Removed the normal-user `Preview portable profile API` action from Profile & Contacts.
- Kept the portable profile backend APIs for developer and connected-app use.
- Added Applications app catalog visibility for YGIT and YGIT Dev.
- Improved Keycloak central-session client alias detection for app/backend names.
- Added TXT and CSV account data download actions under Preferences → Privacy & data.
- Set dark theme as the default for new users and fallback rendering.

## Deployment

- No database migration is required.
- No Keycloak realm/theme change is required.
- Redeploy only the `vib-id-account-portal` service.

## Verification

- Profile page must not display API preview controls.
- Applications page must show YGIT and YGIT Dev even with no service history.
- Download TXT/CSV must work for authenticated users and must not include tokens or secrets.
- Existing portable profile API and internal service profile API must continue to work.
