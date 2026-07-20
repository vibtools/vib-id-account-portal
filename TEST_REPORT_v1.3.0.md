# Test Report — v1.3.0_ACCOUNT_EXPERIENCE

## Static checks completed in sandbox

- Python compileall: PASS
- Ruff check: PASS
- Jinja template parsing: PASS, 20 templates
- Release integrity script: PASS
- Python line-length scan: PASS, no lines over 100 characters

## Automated tests

- Pytest: PASS
- Result: 72 passed / 0 failed
- Coverage gate: PASS
- Total coverage: 90.53%
- Required coverage: 90%

## Tests added

- Profile avatar upload, deletion, validation, and media retrieval.
- Portable profile API for the current user.
- Internal connected-app portable profile API with service-token protection.
- Social profile links create/update/delete/private visibility behavior.
- Applications page YGIT/YGIT Dev central-session fallback.
- Repository-level account-experience persistence helpers.
- Invalid media, invalid subject, invalid service token, and missing avatar paths.

## Remaining deployment-gate checks

- Run Alembic migration in staging/production before app smoke approval.
- Run final Coolify container health checks after deployment.
- Run VPS-side image/security scan if available in production tooling.
