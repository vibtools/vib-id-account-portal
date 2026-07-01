# Operations

## Health

- `/health/live`: process liveness only.
- `/health/ready`: PostgreSQL and OIDC discovery readiness with safe status labels.

## Routine jobs

Run `vib-id cleanup` daily. Run PostgreSQL backups according to the recovery objective. Review failed login, session revocation, and internal-service rejection events. Monitor database pool saturation, response latency, error rate, and Keycloak management circuit state.

## Service registry

Registry changes are CLI-only. Register a service after its OIDC integration and internal client have passed security review. Deactivate metadata rather than deleting historical references.

## Scaling

The database-backed session and rate-limit design supports multiple instances. Start with one instance. Before scaling, measure PostgreSQL connection capacity, set a total pool budget across replicas, and verify sticky sessions are not required.

## Keycloak outage

Existing local portal sessions remain available until their portal timeout, while provider-dependent status degrades safely. New login and token refresh require Keycloak. Avoid repeatedly restarting the portal during an identity-provider incident.

## Database outage

Readiness fails and authenticated operations cannot complete. Restore database connectivity before accepting traffic. Do not switch to an unvalidated fallback store.
