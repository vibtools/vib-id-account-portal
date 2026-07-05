# Vib ID Account Portal v1.2.1 Mobile Logout Visibility Hotfix

## Scope
Minimal mobile-only UI hotfix to make the existing sidebar Sign out button reachable and visible on real mobile browsers.

## Files changed
- `app/static/css/app.css`
- `app/static/js/app.js`

## Preserved
- No backend auth logic changed
- No logout route changed
- No CSRF logic changed
- No Jinja/HTML structure changed
- No colors changed
- No theme tokens changed
- No icon set changed
- No database migration
- No Keycloak configuration change

## Root cause
Real mobile browsers can report `100vh` differently from the actually visible viewport because of browser chrome/address bars and safe-area/gesture areas. The drawer footer existed in HTML but could be clipped below the visible screen.

## Fix
- Use a visual viewport CSS variable with `100dvh` fallback for mobile drawer height.
- Keep the existing sidebar logout form and visual style.
- Make the existing `.sidebar-logout` sticky at the bottom of the drawer on mobile.
- Add safe-area bottom padding to avoid gesture/nav bar clipping.

## Verification performed in source package
- Python compileall: PASS
- Jinja template parsing: PASS, 20 templates
- JavaScript syntax check: PASS
- Patch scope review: PASS

## Deployment target
Only `id.vib.tools` portal service.
Do not restart Keycloak.
Do not edit database.
Do not change secrets.
