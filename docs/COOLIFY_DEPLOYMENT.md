# Coolify Production Deployment

## Target

- Project: **Vib Tools Core**
- Environment: **Production**
- Application: **vib-id-portal**
- Domain: `https://id.vib.tools`
- Container port: `8000`

## 1. PostgreSQL resource

Create a dedicated PostgreSQL resource named `vib-id-postgres`. Use a unique database, user, and generated password. Keep it on the Coolify private network and do not publish port 5432. Enable persistent storage and scheduled encrypted backups.

## 2. Application source and build

Create a Dockerfile-based application from the release repository. Build target is the final runtime stage. The image runs as UID/GID 10001 and listens on container port 8000. Do not publish host port 8000 because the Coolify dashboard already uses that host port; attach the application domain to internal container port 8000 through Coolify's proxy.

## 3. Environment

Copy variable names from `.env.example` into Coolify secrets. Generate the four application secrets with `python scripts/generate_secrets.py`. Use the private PostgreSQL hostname in `DATABASE_URL`. Inspect the `coolify-proxy` Docker network and set `FORWARDED_ALLOW_IPS` to its exact private IP or narrow CIDR; do not use a public wildcard. This is required for correct client-IP rate limiting and forwarded HTTPS scheme handling.

## 4. Identity clients

Configure both Keycloak clients exactly as documented in `KEYCLOAK_CLIENT_SETUP.md`. Verify the interactive callback is exactly `https://id.vib.tools/auth/callback` and the post-logout URI is exact.

## 5. Migration

Before switching application traffic, run one controlled command in a one-off deployment shell:

```bash
alembic upgrade head
```

Do not run migrations automatically in every replica. For concurrent deployment automation, acquire a PostgreSQL advisory lock around the migration command.

## 6. Domain and health checks

Attach `id.vib.tools`, enable managed TLS, force HTTPS, and set the health path to `/health/live`. Use `/health/ready` for deployment readiness checks. The readiness endpoint returns 503 if PostgreSQL or required OIDC discovery is unavailable.

## 7. Runtime hardening

Enable read-only root filesystem, a small writable `/tmp` tmpfs, no-new-privileges, and dropped Linux capabilities when available. Start with one replica and one Uvicorn worker. Suggested initial memory limit is 256–384 MiB and CPU limit is 0.5–1 core.

## 8. Deployment verification

- `/health/live` returns 200.
- `/health/ready` returns 200 without secrets.
- Unauthenticated `/` redirects to `/login` and then the exact Keycloak authorization endpoint with PKCE S256.
- Callback creates a host-only secure cookie and no token appears in browser storage.
- Profile, preferences, local session revocation, and read-only services work.
- Security headers and no-store caching are present.
- Internal endpoint rejects missing, user, forged, expired, or unapproved tokens.

## 9. Rollback

Keep the prior image available. If the migration is backward compatible, switch traffic to the prior image. If a schema rollback is required, take a verified database backup first and run the specific Alembic downgrade only after reviewing data-loss effects.

## 10. Backups and restore

Use Coolify/PostgreSQL scheduled backups plus an independent encrypted copy. Restore into a new private database, run validation queries, point a staging portal at it, verify record counts and login flows, then schedule the production cutover.

## 11. Incident checks

Review application request IDs, Keycloak audit events, database health, recent deployments, certificate state, and reverse-proxy logs. Never paste tokens, cookies, secrets, or full database URLs into tickets.
