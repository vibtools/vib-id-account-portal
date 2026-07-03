# Vib ID Account Portal — Independent Forensic Audit Report

**Version:** 1.1.0
**Audit date:** 2026-07-03
**Target:** `https://id.vib.tools`
**Identity authority:** `https://auth.vib.tools/realms/vib`

## 1. Executive conclusion

Version 1.1.0 is a controlled redesign of the audited v1.0.1 production source. It preserves the identity, authorization, persistence, and deployment architecture while replacing the user-facing portal shell and component system. No known functional or security regression was identified in the source, automated, browser, or visual audit.

**Source release disposition:** PASS.
**Target deployment disposition:** requires the normal image rebuild, health check, and live smoke test after deployment.

## 2. Architecture and backward compatibility

Verified unchanged:

- Keycloak remains the sole authority for credentials, primary email verification, password reset, TOTP, recovery, and central identity sessions.
- Portal identity remains keyed by validated OIDC `sub`.
- Authorization Code Flow with PKCE S256 and signed token validation remains intact.
- Browser receives only a secure opaque portal session cookie.
- Token material remains encrypted at rest and absent from browser storage/templates.
- User-owned data access remains subject-scoped.
- State-changing browser routes remain POST plus CSRF protected.
- Connected services remain browser read-only.
- PostgreSQL schema and Alembic migration head are unchanged.
- Production container continues to run as UID/GID 10001 with dropped capabilities and read-only-root compatibility.

## 3. v1.1.0 security review

| Review item | Result |
|---|---:|
| Authentication and OIDC validation | Preserved |
| Authorization and IDOR protections | Preserved; regression tests passed |
| CSRF protection | Preserved; quick-theme route included |
| Open redirect protection | PASS; explicit route allowlist |
| Browser token/secret storage | None introduced |
| Remote runtime assets | None introduced |
| Unsafe HTML/template construction | No finding |
| Static asset failure handling | PASS |
| Bandit application scan | 0 findings |
| Release placeholder/secret scan | PASS |

## 4. Performance review

- No client framework was added.
- No new production package was added.
- CSS, JavaScript, SVG, and PNG resources are local and version-fingerprinted.
- Essential page content is server rendered.
- JavaScript enhancement is deferred and compact.
- Theme changes use server-side preferences and a small local preview layer.
- Images declare dimensions to reduce layout shift.
- Persistent heavy box shadows and expensive decorative layers were removed.

## 5. Accessibility and UX review

- Semantic navigation landmarks retained.
- Keyboard command palette and Escape handling added.
- Focus-visible treatment audited.
- Controls maintain practical touch/click target sizes.
- Statuses include text, not color alone.
- Responsive navigation prevents desktop controls from crowding mobile layouts.
- Automated browser checks found no horizontal overflow at audited widths.

## 6. Static and automated verification

| Check | Result |
|---|---:|
| Python compilation | Passed |
| Ruff format | Passed; 73 files |
| Ruff lint | Passed |
| mypy strict mode | Passed; 54 source files |
| Unit/integration/security/browser tests | 52 passed, 0 failed |
| Branch-aware coverage | 90.12% |
| Coverage gate | Passed; minimum 90% |
| Bandit | 0 findings |
| Jinja parsing | 14 templates passed |
| JavaScript syntax | Passed |
| `uv.lock` consistency | Passed; 90 packages |
| Release integrity scan | Passed |
| Visual states captured | 14 |
| Browser console errors | 0 |
| Horizontal-overflow findings | 0 |

## 7. Environment-limited verification

The current audit container did not provide Docker and could not resolve `pypi.org` for `pip-audit`. Therefore:

1. A final container-image rebuild and image vulnerability scan must be performed in the deployment environment.
2. Network-enabled `pip-audit -r requirements.txt` must be rerun during release CI or deployment review.
3. After replacing the approved logo files and deploying, execute live login, profile, theme, session, logout, and responsive smoke tests.

These are deployment gates rather than known source defects.

## 8. Final disposition

- **v1.0.1 backend/security baseline:** preserved.
- **v1.1.0 source and UI implementation:** passed.
- **v1.1.0 automated regression suite:** passed.
- **v1.1.0 visual forensic audit:** passed.
- **Production artifact:** approved for deployment, subject to Section 7 operational verification.
