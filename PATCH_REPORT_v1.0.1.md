# Vib ID Account Portal v1.0.1 — Forensic Patch Report

This release supersedes the uploaded v1.0.0 archive.

## Blocking repairs

- Corrected Keycloak service-account identity validation.
- Corrected Docker health checks under strict trusted-host enforcement.
- Removed the Coolify host port 8000 conflict.
- Added transaction locks for concurrency-sensitive first writes.
- Corrected profile optimistic locking.

## Security and resilience repairs

- Enforced OIDC discovery endpoint origin.
- Disabled ambient proxy inheritance for identity-provider requests.
- Added graceful identity-provider failure paths.
- Added fail-closed malformed Keycloak Admin API response handling.
- Added live email-verification state fallback behavior.
- Added standards-aware email contact validation.
- Added bounded future timestamp validation for service events.
- Added static asset version fingerprints.

## Verification

- 48 tests passed.
- Coverage 90.17%.
- Ruff, mypy, Bandit, templates, JavaScript, lock validation, release integrity, offline migration SQL, and production-shaped liveness checks passed.
