# Vib ID Account Portal — Test Report

**Version:** 1.0.1
**Execution date:** 2026-07-01
**Environment:** Linux x86_64; Python 3.13.5; Node.js 22.16.0

## Automated suite

```text
48 passed
0 failed
90.17% branch-aware coverage
90% configured coverage gate passed
```

The suite covers configuration, OIDC/PKCE, signed-token validation, Keycloak management failure behavior, opaque sessions, encryption, CSRF, IDOR prevention, profile/contact validation, concurrency-sensitive repositories, preferences, activities, session revocation, connected services, internal service tokens, web security, and Playwright-rendered mobile/tablet/desktop behavior.

## Static verification

- Python compileall: passed.
- Ruff formatting: passed; 73 files.
- Ruff lint: passed.
- mypy: passed; 54 source files.
- Bandit: 0 findings.
- Jinja parsing: 14 templates passed.
- JavaScript syntax: passed.
- `uv.lock --check`: passed; 90 packages.
- Release integrity: passed.
- Offline Alembic PostgreSQL SQL: passed; 201 lines.

## Runtime-shaped verification

- Production-shaped Uvicorn startup: passed.
- Packaged Docker health-check request: passed.
- Trusted Host allowlist: accepted `id.vib.tools`; rejected an untrusted hostname.
- Unauthenticated root redirect: passed.
- Security headers: passed.

## External checks still required

- Docker image build and scanner.
- PostgreSQL online migration and Compose suite.
- Live Keycloak OIDC browser journey and Admin API tests.
- `pip-audit` in a network-enabled runner. The audit command was attempted but could not resolve `pypi.org`.
