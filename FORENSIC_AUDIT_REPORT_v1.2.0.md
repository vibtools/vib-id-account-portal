# Vib ID Account Portal v1.2.0 — Forensic Audit Report

**Version:** 1.2.0  
**Audit date:** 2026-07-04  
**Baseline:** v1.1.0 production source

## Executive conclusion

Version 1.2.0 preserves the v1.1.0 portal baseline and adds a native account-security module under `id.vib.tools`. The release avoids Keycloak Account Console CSS/PatternFly overrides and keeps Keycloak as the identity authority. No source-level functional or security regression was identified by the completed offline audit gates.

**Source release disposition:** PASS.  
**Deployment disposition:** approved for controlled staging deployment after normal image rebuild, live health checks, vulnerability scan, and smoke test.

## Architecture review

Verified preserved:

- Keycloak remains the sole authority for credentials, email verification, password reset, TOTP, tokens, and central sessions.
- Portal identity remains keyed by validated OIDC `sub`.
- Authorization Code Flow with PKCE S256 remains intact.
- Browser receives only a secure opaque portal session cookie.
- Token material remains encrypted at rest and absent from browser templates.
- State-changing browser routes remain CSRF protected.
- No database migration is introduced.

## Security review

| Review item | Result |
|---|---:|
| Authentication and OIDC validation | Preserved |
| Native security pages require auth | PASS |
| CSRF on sensitive actions | PASS |
| Rate limiting on sensitive actions | PASS |
| Audit logging on sensitive actions | PASS |
| Password/TOTP secret handling | Keycloak-only |
| Token/secret exposure in templates | None found |
| Keycloak Account Console CSS hack | Not used |
| Bandit application scan | 0 findings |
| Release placeholder/secret scan | PASS |

## Performance review

- No new production dependency was added.
- No client framework was added.
- New pages are server-rendered Jinja templates.
- New UI reuses existing CSS/components.
- Keycloak calls are bounded by existing HTTP timeout/circuit behavior.
- Central session details fail closed and do not block local portal session management.

## Accessibility and UX review

- New pages reuse the v1.1.0 page header, panels, tables, forms, statuses, focus behavior, and responsive shell.
- Recovery codes use a safe disabled state instead of fake or unsupported credential generation.
- Applications page uses a read-only table consistent with existing service history.

## Remaining deployment gates

1. Rebuild production image in Coolify.
2. Run Alembic current and confirm unchanged migration head.
3. Run `/health/live` and `/health/ready` checks.
4. Run live smoke tests for login, security pages, password action email, email verification, 2FA action email, sessions, applications, and logout.
5. Run network-enabled dependency scan and container-image vulnerability scan.
