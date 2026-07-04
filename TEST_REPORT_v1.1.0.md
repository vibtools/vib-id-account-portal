# Vib ID Account Portal v1.1.0 — Test Report

**Test date:** 2026-07-03  
**Python:** 3.13.5  
**Application version:** 1.1.0

## Automated verification

| Check | Result |
|---|---:|
| Python compilation | PASS |
| Ruff formatting | PASS — 73 files |
| Ruff lint | PASS |
| mypy strict mode | PASS — 54 source files |
| Pytest unit/integration/security/browser suite | PASS — 52/52 |
| Branch-aware coverage | PASS — 90.12% |
| Required coverage gate | PASS — minimum 90% |
| Bandit security scan | PASS — 0 findings |
| Jinja2 template parsing | PASS — 14 templates |
| JavaScript syntax | PASS |
| `uv.lock` consistency | PASS — 90 resolved packages |
| Release integrity scan | PASS |

## Browser and visual verification

Audited states:

- Overview — desktop dark, desktop light, mobile dark
- Profile & Contacts — desktop dark, desktop light, mobile dark
- Security — desktop dark
- Sessions — desktop dark and mobile dark
- Connected Services — desktop dark
- Activity — desktop dark
- Preferences — desktop dark
- Command palette — desktop dark
- Mobile navigation drawer — dark

Automated visual diagnostics:

- Browser console errors: 0
- Horizontal-overflow findings: 0
- Responsive viewports: desktop and 390px-class mobile
- Keyboard command-palette workflow: PASS
- Public error page keyboard focus and responsive layout: PASS

## Known non-blocking warning

The test environment reports one upstream Starlette/FastAPI `TestClient` deprecation warning concerning the future `httpx2` transition. It does not affect the production Uvicorn runtime or current test correctness.

## Environment-limited checks

- `pip-audit` could not contact `pypi.org` because DNS/network access was unavailable in the audit container. No vulnerability result is claimed from that attempt.
- Docker was not installed in the audit container, so the final image was not rebuilt here. The Dockerfile and Compose topology are unchanged from the deployed v1.0.1 baseline except for packaged application content.
