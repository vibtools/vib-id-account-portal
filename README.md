# Vib ID Account Portal

Vib ID Account Portal is the central user-facing account center for Vib Tools and approved Vib-owned services. Authentication remains exclusively at `auth.vib.tools` through OpenID Connect Authorization Code Flow with PKCE S256.

## Version 1.1.0

The v1.1.0 release preserves the complete v1.0.1 security and account architecture while replacing the portal interface with the Vib Tools design system:

- Flat, border-led surfaces with restrained elevation
- Compact Inter-based typography and JetBrains Mono metadata
- Dark, light, and system themes
- High-information-density desktop layouts
- Responsive navigation drawer and mobile-safe forms/tables
- Keyboard-first command palette with `Ctrl/Cmd+K` or `/`
- Quick appearance control that preserves all other preferences
- Accessible focus indicators, semantic status colors, and progressive enhancement
- No client framework or external runtime asset dependency

## Brand assets

The portal intentionally uses fixed local asset filenames so final approved exports can be replaced without changing templates or CSS:

```text
app/static/brand/vibtools-horizontal-dark.png
app/static/brand/vibtools-horizontal-light.png
app/static/brand/vibtools-icon-dark.png
app/static/brand/vibtools-icon-light.png
app/static/brand/vibtools-favicon.png
```

Replace those files before the public GitHub release while keeping the filenames and transparent PNG format unchanged. See `app/static/brand/README.md`.

## Security model

- Browser receives only a random opaque session cookie.
- Raw session identifiers are never stored in PostgreSQL; only SHA-256 hashes are persisted.
- OIDC token bundles are encrypted at rest with Fernet authenticated encryption.
- Keycloak owns credentials, primary email, verification, TOTP, recovery, token issuance, and global authentication sessions.
- The portal owns extended profiles, preferences, local sessions, activity, and read-only service-connection history.
- The immutable identity key is the validated OIDC `sub` claim.
- Every browser state change is POST-protected with a session-bound CSRF token.
- The internal service-touch endpoint accepts only allowlisted Keycloak service-account tokens with the required role.
- The quick-theme endpoint uses an explicit internal redirect allowlist and cannot be used as an open redirect.

## Runtime and dependencies

- Python 3.13
- FastAPI and Uvicorn
- Jinja2 server-rendered HTML
- SQLAlchemy 2 async and PostgreSQL
- Alembic
- Authlib PKCE generation and JOSE/JWT validation
- HTTPX
- Vanilla JavaScript and local CSS/SVG/PNG assets

No new production dependency was added by the v1.1.0 redesign.

## Local development

1. Copy `.env.example` to `.env` and generate independent secrets:

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

Core pages and forms remain usable without JavaScript. JavaScript provides the responsive drawer, command palette, popovers, theme preview, and confirmation enhancement.

## Keyboard workflow

- `Ctrl/Cmd+K`: open command palette
- `/`: open command palette when focus is not inside an input
- `Arrow Up/Down`: move through visible command results
- `Enter`: activate the selected result
- `Escape`: close the command palette, popover, or mobile navigation
- `Tab` / `Shift+Tab`: standard keyboard navigation throughout the portal

## Verification

Run the complete offline audit suite:

```bash
uv run bash scripts/run_audit.sh
```

The deterministic suite uses mocked OIDC/JWKS services and SQLite for fast execution. Set `TEST_DATABASE_URL` to a PostgreSQL async URL, or run `docker compose -f compose.test.yaml up --build --abort-on-container-exit`, for migration-first PostgreSQL tests.

The v1.1.0 audited release passed 52 tests with 90.12% branch-aware coverage, Ruff, mypy strict mode, Bandit, template parsing, JavaScript syntax, release integrity, and responsive browser checks.

## Operational commands

```bash
uv run vib-id service register --service-key ygit-net --display-name "YGit" --domain ygit.net --description "Git collaboration for Vib users."
uv run vib-id service list
uv run vib-id service deactivate ygit-net
uv run vib-id cleanup
```

## Deployment

Use the production `Dockerfile` and `docs/COOLIFY_DEPLOYMENT.md`. Database migrations remain a distinct deployment step and are not run by every application replica. The v1.1.0 release contains no schema migration; deploy it over the existing v1.0.1 database after backup and standard health checks.
