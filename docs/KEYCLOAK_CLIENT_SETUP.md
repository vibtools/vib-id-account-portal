# Keycloak Client Setup

Production realm issuer:

```text
https://auth.vib.tools/realms/vib
```

## Interactive client: `vib-id-portal`

- Client type: OpenID Connect
- Client authentication: On
- Standard flow: On
- Direct access grants: Off
- Implicit flow: Off
- Service accounts: Off
- PKCE code challenge method: S256
- Valid redirect URI: `https://id.vib.tools/auth/callback`
- Valid post logout redirect URI: `https://id.vib.tools/`
- Web origin: `https://id.vib.tools`
- Default scopes: `openid`, `profile`, `email`
- Root/Home URL: `https://id.vib.tools`

Copy the generated client secret to Coolify secret storage as `OIDC_CLIENT_SECRET`. Do not place it in the repository.

## Management client: `vib-id-portal-management`

- Client authentication: On
- Standard flow: Off
- Direct access grants: Off
- Implicit flow: Off
- Service accounts: On
- Browser login and consent: Off

Assign only the realm-management roles required by enabled operations:

- `view-users` for reading the authenticated user, credentials status, and session count.
- `manage-users` only when central logout is enabled.

Do not assign realm-admin, client management, role management, impersonation, or user creation privileges. Store its secret as `KEYCLOAK_MANAGEMENT_CLIENT_SECRET`.

## Internal SaaS clients

Each approved backend uses a separate confidential service-account client. Name it `${service_key}-backend` (for example, `ygit-net-backend`) or exactly the registered service key. Add a dedicated realm role named `service-connections:touch`, map it only to approved service accounts, configure the token audience expected by `KEYCLOAK_MANAGEMENT_AUDIENCE`, and add the client ID to `KEYCLOAK_ALLOWED_INTERNAL_CLIENTS`. Runtime authorization verifies Keycloak's `preferred_username=service-account-${client_id}` convention and binds the caller client ID to that one service key, preventing an approved backend or end-user token from recording activity for another service.

## Verification

Confirm discovery returns the exact issuer, authorization endpoint, token endpoint, JWKS URI, and end-session endpoint. Test invalid redirect URIs, direct access grants, and end-user tokens; they must be rejected.
