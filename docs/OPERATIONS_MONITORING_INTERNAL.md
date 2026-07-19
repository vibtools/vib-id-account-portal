# Vib ID Private Operations Monitoring

## Scope

This is an internal operator-only monitoring workflow for `auth.vib.tools` and `id.vib.tools`.
It is not exposed through user-facing portal routes, templates, navigation, or public APIs.

## Script

```bash
scripts/internal-ops/operations_monitoring.sh
```

## Checks

- `auth.vib.tools` OIDC discovery endpoint returns HTTP 200.
- `id.vib.tools` live health endpoint returns HTTP 200.
- `id.vib.tools` ready health endpoint reports ready status.
- Portal container health is healthy/running.
- Keycloak container health is healthy/running.
- Recent portal logs have no fatal or central identity failures.
- Recent Keycloak logs have no FreeMarker, template, required-action, or forbidden errors.
- Host root filesystem usage is below the configured warning threshold.
- TLS certificate expiry is readable for `auth.vib.tools` and `id.vib.tools`.

## Safe usage

Run manually from the VPS:

```bash
cd /path/to/vib-id-account-portal
scripts/internal-ops/operations_monitoring.sh
```

Optional environment overrides:

```bash
LOG_WINDOW=60m DISK_WARN_PERCENT=80 scripts/internal-ops/operations_monitoring.sh
```

## Public exposure rule

Do not add this script to portal navigation, user templates, public routes, or static assets. It is operational tooling only.

## Secret policy

The script does not print `.env` values, client secrets, database URLs, token encryption keys, CSRF secrets, or private keys.
