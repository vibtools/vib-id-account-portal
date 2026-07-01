# Backup and Restore

## Scope

Back up the dedicated portal PostgreSQL database and deployment configuration kept in secret management. Keycloak has a separate backup plan because it remains the identity source of truth.

## Backup

Use PostgreSQL custom-format backups with encryption in transit and at rest. Keep daily backups, periodic long-retention copies, and at least one copy outside the primary server. Record backup time, database version, schema revision, object size, and checksum.

Example executed from a trusted administrative environment:

```bash
pg_dump --format=custom --no-owner --no-acl "$DATABASE_URL_SYNC" > vib-id-portal.dump
sha256sum vib-id-portal.dump > vib-id-portal.dump.sha256
```

## Restore validation

1. Verify checksum.
2. Restore to a new isolated PostgreSQL database.
3. Run `alembic current` and compare with the expected revision.
4. Check table counts, constraints, and indexes.
5. Start a staging portal with staging OIDC clients.
6. Test login, profile reads, activity pagination, and service history.
7. Document recovery time and data loss window.

Never restore production user data to an unapproved developer workstation.
