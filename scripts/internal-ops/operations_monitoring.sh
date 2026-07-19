#!/usr/bin/env bash
set -Eeuo pipefail

# Vib ID private operations monitor.
# This script is intentionally not mounted in the public portal UI and does not print secrets.

AUTH_OIDC_URL="${AUTH_OIDC_URL:-https://auth.vib.tools/realms/vib/.well-known/openid-configuration}"
PORTAL_LIVE_URL="${PORTAL_LIVE_URL:-https://id.vib.tools/health/live}"
PORTAL_READY_URL="${PORTAL_READY_URL:-https://id.vib.tools/health/ready}"
KEYCLOAK_CONTAINER="${KEYCLOAK_CONTAINER:-keycloak-vlzz5n6gprxkj7zqnc9y1gyq}"
APP_CONTAINER_PREFIX="${APP_CONTAINER_PREFIX:-qssde119mziy5d5gycwxzdjg-}"
DISK_WARN_PERCENT="${DISK_WARN_PERCENT:-85}"
LOG_WINDOW="${LOG_WINDOW:-30m}"

failures=0

section() {
  printf '\n=== %s ===\n' "$1"
}

pass() {
  printf 'PASS: %s\n' "$1"
}

fail() {
  printf 'FAIL: %s\n' "$1"
  failures=$((failures + 1))
}

http_status() {
  local url="$1"
  curl -sS -o /tmp/vib-id-monitor-response.$$ -w '%{http_code}' "$url" || true
}

section "Vib ID private operations monitor"
printf 'Timestamp UTC: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'Mode: internal-ops-only\n'

section "Public health endpoints"
auth_status="$(http_status "$AUTH_OIDC_URL")"
if [ "$auth_status" = "200" ]; then
  pass "auth.vib.tools OIDC discovery returned HTTP 200"
else
  fail "auth.vib.tools OIDC discovery returned HTTP $auth_status"
fi

live_status="$(http_status "$PORTAL_LIVE_URL")"
if [ "$live_status" = "200" ]; then
  pass "id.vib.tools live health returned HTTP 200"
else
  fail "id.vib.tools live health returned HTTP $live_status"
fi

ready_status="$(http_status "$PORTAL_READY_URL")"
if [ "$ready_status" = "200" ] && grep -q '"status":"ready"' /tmp/vib-id-monitor-response.$$; then
  pass "id.vib.tools ready health returned ready"
else
  fail "id.vib.tools ready health check failed with HTTP $ready_status"
fi
rm -f /tmp/vib-id-monitor-response.$$

section "Docker container health"
if command -v docker >/dev/null 2>&1; then
  app_container="$(sudo docker ps --format '{{.Names}}' | grep "^${APP_CONTAINER_PREFIX}" | head -n 1 || true)"
  if [ -n "$app_container" ]; then
    app_health="$(sudo docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$app_container" 2>/dev/null || true)"
    if [ "$app_health" = "healthy" ] || [ "$app_health" = "running" ]; then
      pass "portal container $app_container is $app_health"
    else
      fail "portal container $app_container health is $app_health"
    fi
  else
    fail "portal container not found for prefix ${APP_CONTAINER_PREFIX}"
  fi

  keycloak_health="$(sudo docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$KEYCLOAK_CONTAINER" 2>/dev/null || true)"
  if [ "$keycloak_health" = "healthy" ] || [ "$keycloak_health" = "running" ]; then
    pass "Keycloak container $KEYCLOAK_CONTAINER is $keycloak_health"
  else
    fail "Keycloak container $KEYCLOAK_CONTAINER health is $keycloak_health"
  fi

  section "Recent fatal log scan"
  if [ -n "${app_container:-}" ]; then
    portal_errors="$(sudo docker logs --since "$LOG_WINDOW" "$app_container" 2>&1 | grep -iE 'traceback|exception|500|502|503|400 Bad Request|401|403|central_unavailable|template not found' | tail -n 80 || true)"
    if [ -z "$portal_errors" ]; then
      pass "no recent portal fatal errors found"
    else
      printf '%s\n' "$portal_errors"
      fail "recent portal fatal/error lines found"
    fi
  fi

  keycloak_errors="$(sudo docker logs --since "$LOG_WINDOW" "$KEYCLOAK_CONTAINER" 2>&1 | grep -iE 'freemarker|failed to process template|internal server error|response status 500|execute-actions.*400|send-verify-email.*400|unauthorized|forbidden' | tail -n 80 || true)"
  if [ -z "$keycloak_errors" ]; then
    pass "no recent Keycloak template/action errors found"
  else
    printf '%s\n' "$keycloak_errors"
    fail "recent Keycloak template/action error lines found"
  fi
else
  fail "docker command not available"
fi

section "Host disk usage"
disk_percent="$(df -P / | awk 'NR==2 {gsub("%", "", $5); print $5}')"
if [ -n "$disk_percent" ] && [ "$disk_percent" -lt "$DISK_WARN_PERCENT" ]; then
  pass "root filesystem usage ${disk_percent}% is below ${DISK_WARN_PERCENT}%"
else
  fail "root filesystem usage ${disk_percent}% is at or above ${DISK_WARN_PERCENT}%"
fi

section "TLS certificate visibility"
for host in auth.vib.tools id.vib.tools; do
  if command -v openssl >/dev/null 2>&1; then
    expiry="$(echo | openssl s_client -servername "$host" -connect "$host:443" 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2- || true)"
    if [ -n "$expiry" ]; then
      pass "$host certificate expiry visible: $expiry"
    else
      fail "$host certificate expiry could not be read"
    fi
  else
    fail "openssl command not available for $host certificate check"
  fi
done

section "Summary"
if [ "$failures" -eq 0 ]; then
  printf 'PRIVATE_OPERATIONS_MONITORING_PASS\n'
  exit 0
fi
printf 'PRIVATE_OPERATIONS_MONITORING_FAIL failures=%s\n' "$failures"
exit 1
