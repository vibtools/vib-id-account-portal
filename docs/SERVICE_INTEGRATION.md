# Connected Service Integration

## Purpose

Approved Vib-owned SaaS backends record successful Vib ID authentication so the account portal can show a read-only service history.

## Prerequisites

- A confidential Keycloak service-account client for the backend.
- Expected audience configured for the portal internal endpoint.
- Role `service-connections:touch` mapped to the service account.
- Client ID present in `KEYCLOAK_ALLOWED_INTERNAL_CLIENTS`. The client ID must equal the registered `service_key` or follow the locked `${service_key}-backend` convention; a client approved for one service cannot touch another service.
- Service metadata registered by CLI.

## Register metadata

```bash
vib-id service register \
  --service-key ygit-net \
  --display-name "YGit" \
  --domain ygit.net \
  --description "Git collaboration service for approved Vib users." \
  --sort-order 100
```

## Request

```http
POST /internal/v1/service-connections/touch
Authorization: Bearer <client-credentials-access-token>
Content-Type: application/json

{
  "subject": "validated-central-user-sub",
  "service_key": "ygit-net",
  "authenticated_at": "2026-06-30T12:00:00Z"
}
```

The backend must use the `sub` value obtained from its own validated user OIDC login. It must not send email or other PII. Retry only idempotently with bounded backoff. A successful response is 204.

## Rejections

Missing/forged/expired tokens, end-user tokens, unapproved clients, missing role, unknown service keys, oversized bodies, and rate-limit violations are rejected generically. No browser CORS access is enabled.

## Portable Profile API for Connected Apps

Connected applications can show the same Vib ID profile photo, display name, job title, organization, locale, timezone, and app-visible social links by calling the server-side portable profile endpoint after login.

```http
GET /internal/v1/account-profiles/{subject}
Authorization: Bearer SERVICE_ACCOUNT_ACCESS_TOKEN
```

Rules:

- Use the user `sub` claim from the OIDC login result.
- Call this endpoint from the application backend only.
- Do not call this endpoint from browser JavaScript.
- Do not store service-account tokens in frontend code.
- Cache profile responses briefly and refresh after login or profile update.

This endpoint is separate from OIDC token claims so profile photo and profile details can update centrally without forcing every connected app to redesign its auth flow.


## Application catalog behavior

The user-facing Applications page includes a read-only VibTools app catalog. First-class apps such as YGIT and YGIT Dev are shown even before the account has a local service touch record. A separate service-history section shows actual registry or central-session activity when available.

Central session fallback recognizes canonical frontend and backend client aliases such as `ygit`, `ygit-net`, `ygit-backend`, `ygit-net-backend`, `ygit-dev`, and `ygit-dev-backend`. Backends should still record a service touch after login so the account portal can persist first-connected and last-used timestamps.

## User data export

Users can download account data from Preferences → Privacy & data as TXT or CSV. The export is authenticated, rate-limited, and audit-logged. It includes account profile fields, preferences, contact methods, social links, and connected application history. It never includes passwords, access tokens, refresh tokens, session cookies, CSRF secrets, service-account secrets, or raw Keycloak credential material.

## User interface boundaries

Do not expose API endpoint URLs or service-token instructions in normal user profile screens. End users manage profile information and account data exports in the portal. Developers should use this document for backend-to-backend profile integration.
