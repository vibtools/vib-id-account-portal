# Final Delivery Status — Vib ID Account Portal v1.3.1

## Status

PASS — v1.3.1 account experience hotfix is production-ready for controlled deployment.

## Features Verified

- Profile page no longer exposes `Preview portable profile API`.
- Backend portable profile APIs remain available for connected app developers.
- Applications page displays default VibTools app catalog even when service history is empty.
- Applications service-history behavior remains preserved.
- YGIT/YGIT Dev central-session alias detection is improved.
- Preferences page includes `Download account data` actions for TXT and CSV.
- New users and fallback rendering default to dark theme.
- Existing account/profile/avatar/social-link/security/session features are preserved.

## Deployment Plan

1. Apply patch or merge v1.3.1 branch into `main`.
2. Redeploy only Coolify service `vib-id-account-portal`.
3. Do not run Alembic migration for v1.3.1.
4. Do not restart or edit Keycloak unless unrelated infrastructure requires it.
5. Run health and smoke tests:
   - `/health/live`
   - `/health/ready`
   - `/profile`
   - `/applications`
   - `/preferences`
   - `/preferences/account-data.txt`
   - `/preferences/account-data.csv`
   - `/api/account/profile/portable`

## Rollback Plan

- Revert the application image/commit to v1.3.0.
- No database rollback required because v1.3.1 has no migration.
- Existing v1.3.0 database tables remain compatible.

## Final Decision

Release accepted for deployment.
