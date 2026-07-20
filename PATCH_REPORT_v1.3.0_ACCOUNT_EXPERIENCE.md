# Patch Report — v1.3.0_ACCOUNT_EXPERIENCE

## Baseline

v1.2.2_OPERATIONS_UI_PATCH

## Scope

- Add profile photo upload/remove.
- Add DB-backed profile avatar media serving.
- Add social/profile links management.
- Add portable profile API for connected apps.
- Add internal service-token protected profile API for other VibTools apps.
- Fix Applications page blank state for YGIT/YGIT Dev by reading central Keycloak sessions and known service definitions.
- Add additive migration for account experience data.
- Add account experience tests and documentation.

## Preserved

- Existing login/auth/OIDC flows.
- Existing security module routes.
- Existing email and Keycloak theme behavior.
- Existing operations monitoring.
- Existing session and CSRF protections.
- Existing request-id/header tracing.
- Existing mobile logout hotfix behavior.

## Not changed

- No Keycloak restart required.
- No Keycloak theme change.
- No Keycloak direct database access.
- No destructive DB migration.
- No public monitoring route.
- No raw token exposure.
- No browser-stored profile tokens.

## Safety controls

- Avatar uploads validate MIME type and binary signature.
- SVG/avatar script payloads are rejected.
- Upload size limit is configurable and bounded.
- Social links reject unsafe URL schemes and embedded credentials.
- Portable profile API exposes safe profile fields only.
- Internal profile API requires valid service token.
