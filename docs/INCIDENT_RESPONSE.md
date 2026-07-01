# Incident Response

## Priorities

Protect user sessions and central identity, contain unauthorized access, preserve evidence, restore service safely, and communicate without exposing sensitive data.

## Initial actions

1. Assign an incident owner and severity.
2. Preserve application, reverse-proxy, PostgreSQL, and Keycloak logs with timestamps.
3. Rotate affected client secrets or encryption material using the documented sequence.
4. Revoke affected portal sessions by subject or OIDC session identifier.
5. Disable an affected internal service client in Keycloak and remove it from the allowlist.
6. Deploy a tested remediation and monitor request IDs and rejection rates.

## Suspected token or session compromise

Revoke central sessions, revoke local database sessions, rotate the relevant client secret, and review activity by time range. Do not log or share the compromised material.

## Suspected database disclosure

Restrict database connectivity, rotate database credentials and token-encryption keys through a controlled migration, identify exposed fields, and follow applicable notification obligations.

## Post-incident

Document root cause, timeline, affected scope, evidence, remediation, regression tests, residual risk, and prevention actions. Verify backups and run the complete audit suite before closing.
