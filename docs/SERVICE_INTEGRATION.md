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
