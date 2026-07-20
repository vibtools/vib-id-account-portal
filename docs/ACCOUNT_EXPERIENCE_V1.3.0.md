# Vib ID Account Experience v1.3.0

## Purpose

`v1.3.0_ACCOUNT_EXPERIENCE` extends Vib ID from an account/security portal into a portable identity profile source for connected VibTools applications.

## User-facing additions

- Profile photo upload and remove from `/profile`.
- Central social/profile links: GitHub, LinkedIn, X/Twitter, Facebook, YouTube, Website, Portfolio.
- Applications page now resolves connected apps from both the local service registry and Keycloak central sessions.
- YGIT and YGIT Dev are recognized as first-class connected Vib ID apps.

## Connected-app profile sharing

Connected apps should not scrape portal HTML. After a user signs in through Vib ID, a backend service can use the user `sub` claim and call:

```http
GET /internal/v1/account-profiles/{subject}
Authorization: Bearer SERVICE_ACCOUNT_ACCESS_TOKEN
```

The response is a portable profile object:

```json
{
  "subject": "user-sub",
  "display_name": "User Name",
  "email": null,
  "email_verified": null,
  "preferred_language": "en",
  "timezone": "UTC",
  "country_code": "BD",
  "organization_name": "VibTools",
  "job_title": "Developer",
  "avatar_url": "https://id.vib.tools/media/profile-avatars/...png",
  "social_links": [
    {"platform": "github", "label": "GitHub", "url": "https://github.com/vibtools"}
  ],
  "updated_at": "2026-07-20T00:00:00Z"
}
```

## Security model

- Profile photo files are limited to PNG, JPEG, or WebP.
- SVG is not accepted for profile photos.
- File content signature must match declared content type.
- Request body limit is configurable and remains bounded.
- Social URLs are normalized and block unsafe schemes such as `javascript:`.
- Internal profile API requires a validated Keycloak service-account token.
- User-facing profile mutations require authenticated portal session and CSRF.
- No raw OIDC token is exposed to frontend pages or portable profile responses.

## Operational notes

This release includes an additive database migration:

```text
20260720_0002_account_experience.py
```

It creates:

```text
user_social_links
user_profile_photos
```

No existing table is dropped or rewritten.
