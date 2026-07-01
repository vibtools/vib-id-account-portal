# Vib ID Account Portal — Independent Forensic Audit Report

**Version:** 1.0.1
**Audit date:** 2026-07-01
**Target:** `https://id.vib.tools`
**Identity authority:** `https://auth.vib.tools/realms/vib`

## 1. Executive conclusion

The uploaded v1.0.0 archive was a substantial release candidate, but it was not safe to deploy unchanged. Its own delivery report correctly marked the production gate as conditional because Docker, PostgreSQL, dependency-vulnerability, and live-Keycloak checks were not completed.

An independent source-level and runtime-shaped forensic audit identified additional defects that were not reported in the original delivery. All defects listed as fixed below have been repaired in v1.0.1 and regression-tested.

**Current disposition:** release candidate accepted for controlled staging deployment. Production acceptance remains conditional until the Docker image, PostgreSQL migration, live OIDC journey, and vulnerability/image scans pass on the target infrastructure.

## 2. Release integrity

- Original archive SHA-256 verified against the supplied checksum.
- Archive traversal and symbolic-link checks passed.
- No `.env`, private key, VCS metadata, virtual environment, test cache, or compiled Python artifact is included in the v1.0.1 release archive.
- Deterministic ZIP generation and a separate SHA-256 checksum are provided.

## 3. Independent defects found and repaired

| ID | Severity | Finding in v1.0.0 | v1.0.1 remediation | Status |
|---|---|---|---|---|
| F-01 | Critical functional | Internal service tokens required `sub` to start with `service-account-`. Keycloak service-account tokens use an immutable UUID-like `sub`; the service-account identity is represented by `preferred_username=service-account-${client_id}`. Legitimate SaaS service-touch calls would be rejected. | Validate signed token `sub` normally; require the exact service-account `preferred_username`, allowlisted `azp`, audience, role, issuer, and expiry. | Fixed |
| F-02 | High availability | Docker health check called `127.0.0.1:8000` without an allowed Host header while production trusted-host validation permits only `id.vib.tools`. The healthy application could be marked unhealthy. | Health check derives the hostname from `APP_BASE_URL` and sends the correct Host header. | Fixed |
| F-03 | High deployment | Production Compose bound host port `8000`, colliding with the existing Coolify dashboard on the VPS. | Removed host publication; application exposes only internal container port `8000` for Coolify/Traefik routing. | Fixed |
| F-04 | High concurrency | First-write paths for rate-limit buckets, profile bootstrap, and connected-service records could race under concurrent requests. | Added PostgreSQL transaction-scoped advisory locks around deterministic first-write identities. | Fixed |
| F-05 | High data integrity | Profile optimistic locking reduced timestamp precision and did not lock the target row, allowing close concurrent updates to overwrite each other. | Added row locking and exact timestamp comparison. | Fixed |
| F-06 | Medium security | OIDC discovery URLs were accepted without enforcing the configured issuer origin. Ambient process proxy variables were inherited by HTTPX. | Enforce same scheme/host origin for provider endpoints and set `trust_env=False`. | Fixed |
| F-07 | Medium resilience | Callback and logout provider network failures could surface as unhandled or poor user flows. | Added bounded provider-failure handling and safe local-logout fallback. | Fixed |
| F-08 | Medium resilience | Invalid JSON from the Keycloak Admin API could escape management-client error handling. | Convert malformed management responses into fail-closed availability state. | Fixed |
| F-09 | Medium correctness | Email verification display relied primarily on the login-time ID-token state and could become stale. | Prefer current Keycloak user state, with signed ID-token claim only as fallback. | Fixed |
| F-10 | Medium correctness | Additional contact email validation only checked for an `@` character. | Added standards-aware syntax/IDNA normalization with `email-validator`; DNS deliverability is intentionally not queried. | Fixed |
| F-11 | Medium integrity | Internal service events could claim timestamps arbitrarily far in the future. | Require timezone-aware timestamps and reject values more than five minutes ahead. | Fixed |
| F-12 | Low cache correctness | Long immutable caching was used with unversioned static asset URLs. | Added application-version query fingerprints to static asset references. | Fixed |

## 4. Architecture and authorization review

Verified:

- Keycloak remains the sole identity, password, email-verification, TOTP, recovery, and token authority.
- Portal identity is keyed by validated OIDC `sub`, never by mutable email.
- Authorization Code Flow with PKCE S256, state, nonce, issuer, signature, audience, authorized-party, expiry, and not-before validation is implemented.
- Browser receives only a secure opaque session cookie; raw OIDC tokens are not placed in browser storage.
- Server-side session identifiers are stored only as hashes; token material is authenticated-encrypted at rest.
- All user-owned queries are subject-scoped.
- Connected services are browser read-only.
- No end-user developer console, API key, personal token, client-secret, raw-JWT, OAuth-client, webhook, or scope-management interface exists.
- State-changing browser routes use POST plus CSRF validation.
- Internal service tracking requires a signed, allowlisted, role-bearing service-account token and cryptographically binds the caller to one service key.

## 5. Static and automated verification

| Check | Result |
|---|---:|
| Python compilation | Passed |
| Ruff format | Passed; 73 files |
| Ruff lint | Passed |
| mypy | Passed; 54 source files |
| Unit/integration/security/browser tests | 48 passed, 0 failed |
| Branch-aware coverage | 90.17% |
| Coverage gate | Passed; minimum 90% |
| Bandit | 0 findings |
| Jinja parsing | 14 templates passed |
| JavaScript syntax | Passed |
| `uv.lock` consistency | Passed; 90 packages |
| Release integrity scan | Passed |
| Offline Alembic PostgreSQL SQL generation | Passed; 201 lines |

One test-only Starlette/FastAPI `TestClient` deprecation warning remains. It does not affect the production runtime and should be revisited when the upstream migration is stable.

## 6. Runtime-shaped verification

Using production validation settings and the packaged runtime entry point:

- Uvicorn startup passed.
- Exact Docker health-check logic returned `{"status":"ok"}`.
- Correct Host header returned HTTP 200.
- Untrusted Host header returned HTTP 400.
- Unauthenticated root returned the expected login redirect.
- Production security headers were present.
- Fail-closed configuration validation remained active.

## 7. Deployment asset review

- Multi-stage Dockerfile.
- Non-root runtime UID/GID 10001.
- `no-new-privileges`, dropped Linux capabilities, read-only filesystem-compatible design, and temporary `/tmp` support are defined in Compose.
- PostgreSQL is private and persistent.
- Database migration remains a distinct controlled step.
- Host port 8000 is no longer published.
- Coolify must route `https://id.vib.tools` to container port 8000.

## 8. Open external production gates

The following cannot be honestly marked passed in this audit environment and must be executed on the target VPS/staging environment:

1. Build the final Docker image.
2. Inspect final runtime user and filesystem behavior.
3. Start a real PostgreSQL database and execute Alembic upgrade, downgrade rehearsal, and re-upgrade on staging data.
4. Run the full Compose PostgreSQL test target.
5. Create the real Keycloak interactive and management clients and execute browser login, callback, refresh, logout, 2FA-state, email-state, session, and back-channel-logout tests.
6. Run `pip-audit -r requirements.txt` in a network-enabled environment. The current attempt failed only because `pypi.org` DNS resolution was unavailable.
7. Scan the final container image and resolve every High/Critical result.
8. Validate backup and restore before production user onboarding.

## 9. Final audit disposition

- **Original v1.0.0 direct production deployment:** Rejected.
- **Patched v1.0.1 source quality:** Passed.
- **Patched v1.0.1 controlled staging deployment:** Approved.
- **Production acceptance:** Conditional until Section 8 completes without a blocking defect.
