# Vib ID Account Portal

`id.vib.tools` is the central user-facing account center for Vib Tools and approved Vib-owned services. Authentication remains exclusively at `auth.vib.tools` through OpenID Connect Authorization Code Flow with PKCE S256.

## Security model

- Browser receives only a random opaque session cookie.
- Raw session identifiers are never stored in PostgreSQL; only SHA-256 hashes are persisted.
- OIDC token bundles are encrypted at rest with Fernet authenticated encryption.
- Keycloak owns credentials, primary email, verification, TOTP, recovery, token issuance, and global authentication sessions.
- The portal owns extended profiles, preferences, local sessions, activity, and read-only service-connection history.
- The immutable identity key is the validated OIDC `sub` claim.
- Every browser state change is POST-protected with a session-bound CSRF token.
- The internal service-touch endpoint accepts only allowlisted Keycloak service-account tokens with the required role.

## Runtime

- Python 3.13
- FastAPI and Uvicorn
- Jinja2 server-rendered HTML
- SQLAlchemy 2 async and PostgreSQL
- Alembic
- Authlib PKCE generation with standards-based JOSE/JWT validation through `joserfc`
- HTTPX
- Vanilla JavaScript and local CSS/SVG assets

## Local development

1. Create `.env` from `.env.example` and generate independent secrets:

   ```bash
   python scripts/generate_secrets.py
   ```

2. Set development-safe local URLs and PostgreSQL credentials. Development mode is enabled only with `APP_ENV=development`.
3. Install locked dependencies:

   ```bash
   uv sync --all-groups --locked
   ```

4. Run migrations:

   ```bash
   uv run alembic upgrade head
   ```

5. Start the portal:

   ```bash
   uv run python -m app.run
   ```

Core pages work without JavaScript. JavaScript provides mobile navigation, theme preview, and filter auto-submit enhancement.

## Verification

```bash
uv run bash scripts/run_audit.sh
```

The default isolated suite uses deterministic mocked OIDC/JWKS services and SQLite for fast execution. Set `TEST_DATABASE_URL` to a PostgreSQL async URL, or run `docker compose -f compose.test.yaml up --build --abort-on-container-exit`, to execute migration-first repository and route tests against PostgreSQL.

## Operational commands

```bash
uv run vib-id service register --service-key ygit-net --display-name "YGit" --domain ygit.net --description "Git collaboration for Vib users."
uv run vib-id service list
uv run vib-id service deactivate ygit-net
uv run vib-id cleanup
```

## Deployment

Use the production `Dockerfile` and `docs/COOLIFY_DEPLOYMENT.md`. Database migrations are a distinct deployment step and are not run by every application replica.
