# Test Report — Vib ID Account Portal v1.3.1

## Environment

- Python: 3.13
- Database: test SQLite via project test harness
- Baseline: v1.3.0 account experience package
- Target: v1.3.1 account experience hotfix

## Commands Executed

```bash
python -m compileall app tests scripts
python -m ruff check app tests scripts
python -m pytest -q
git diff --check
```

## Results

| Check | Result |
|---|---:|
| Compile | PASS |
| Ruff | PASS |
| Pytest | PASS |
| Coverage gate | PASS |
| Git whitespace check | PASS |
| User-facing API preview removed | PASS |
| Applications catalog visible | PASS |
| Account TXT/CSV export | PASS |
| Default dark theme fallback | PASS |
| Brand assets untouched | PASS |
| `.env` untouched | PASS |

## Pytest Summary

```text
78 passed
Required test coverage of 90% reached.
Total coverage: 90.17%
```

## Security Review

- Account data export requires authenticated portal session.
- Account data export is rate-limited and audit-logged.
- Export responses use `Cache-Control: no-store`.
- Export does not include access tokens, refresh tokens, session IDs, session cookies, CSRF secrets, service-account secrets, passwords, or raw credential data.
- Developer-only profile APIs remain backend/API features and are not promoted from normal user profile UI.
- No secret file or environment file added.
- No database destructive change added.

## Known Deployment Note

No migration is required for v1.3.1. Deploy only the `vib-id-account-portal` service.
