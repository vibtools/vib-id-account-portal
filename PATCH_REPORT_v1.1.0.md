# Vib ID Account Portal v1.1.0 — Patch Report

This release supersedes v1.0.1 for the user-facing portal while retaining its backend, security, and deployment architecture.

## User-interface repairs

- Replaced shadow-heavy dashboard surfaces with flat, border-led panels.
- Reduced oversized typography and excessive whitespace.
- Added a compact top bar and high-density account navigation.
- Added complete dark, light, and system theme styling.
- Added responsive drawer navigation and mobile-safe content layouts.
- Added explicit final-logo replacement slots for dark/light horizontal and icon assets.
- Added image fallback handling to avoid broken-brand layout states.

## Workflow improvements

- Added global keyboard command search with `Ctrl/Cmd+K` and `/`.
- Added quick theme switching without overwriting other preferences.
- Added coordinated popover, drawer, and Escape-key behavior.
- Preserved no-JavaScript operation for essential pages and forms.

## Security and data integrity

- Preserved all v1.0.1 identity controls.
- Quick-theme mutations are CSRF protected.
- Post-action redirects use a strict internal allowlist.
- No raw tokens, credentials, or new client-side persistence were introduced.
- No schema change or new production dependency was introduced.

## Verification

- 52 automated tests passed.
- Branch-aware coverage: 90.12%.
- Ruff format and lint: passed.
- mypy strict mode: passed for 54 source files.
- Bandit: zero findings.
- 14 Jinja templates parsed.
- JavaScript syntax: passed.
- Visual audit: 14 desktop/mobile/theme states; zero console errors and zero horizontal-overflow findings.
