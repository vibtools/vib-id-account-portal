# Vib ID Account Portal v1.2.0 — Test Report

**Test date:** 2026-07-04  
**Python:** 3.13.5  
**Application version:** 1.2.0

## Automated verification

| Check | Result |
|---|---:|
| Python compilation | PASS |
| Ruff formatting | PASS — 78 files |
| Ruff lint | PASS |
| mypy strict mode | PASS — 58 source files |
| Pytest unit/integration/security/browser suite | PASS — 56/56 |
| Branch-aware coverage | PASS — 90.35% |
| Required coverage gate | PASS — minimum 90% |
| Bandit application scan | PASS — 0 findings |
| Jinja2 template parsing | PASS — 20 templates |
| JavaScript syntax | PASS |
| Release integrity scan | PASS |

## Security-module verification

- Native security pages return HTTP 200 for authenticated users
- No raw server-side token appears in rendered pages
- User-facing Keycloak Account Console links are removed from native pages
- Password required-action request is CSRF protected, rate limited, and audit logged
- Email verification resend and email-change request are protected and audit logged
- 2FA enable and disable requests are protected and audit logged
- Security session revoke and logout-all routes are protected and audit logged
- Application consent revocation requires `X-CSRF-Token`
- Keycloak-management failure paths return controlled user messages

## Environment-limited checks

- `pip-audit` was not available in this sandbox runtime, so dependency vulnerability scanning must be run in CI/VPS.
- Docker/image vulnerability scanning was not available in this sandbox runtime and remains a deployment gate.
