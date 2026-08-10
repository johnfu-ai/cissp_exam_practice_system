#!/usr/bin/env bash
# Docker-stack smoke for §14 critical paths (health + auth + practice create).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API="${API_BASE_URL:-http://localhost:8000}"
EMAIL="${SMOKE_EMAIL:-admin@example.com}"
PASSWORD="${SMOKE_PASSWORD:-admin}"

echo "==> GET $API/health"
curl -sf "$API/health" | grep -q '"status":"ok"'

echo "==> POST /api/auth/login"
LOGIN=$(curl -sf -X POST "$API/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")
TOKEN=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])' <<<"$LOGIN")

echo "==> GET /api/auth/me"
curl -sf "$API/api/auth/me" -H "Authorization: Bearer $TOKEN" | grep -q email

echo "==> GET /api/domains"
curl -sf "$API/api/domains" -H "Authorization: Bearer $TOKEN" >/dev/null

echo "==> POST /api/practice/sessions (may 422 if no published bank)"
CODE=$(curl -s -o /tmp/e2e_practice.json -w '%{http_code}' -X POST \
  "$API/api/practice/sessions" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"count":1,"order_mode":"random","subset":"all"}')
if [[ "$CODE" != "200" && "$CODE" != "422" ]]; then
  echo "unexpected practice create status: $CODE" >&2
  cat /tmp/e2e_practice.json >&2
  exit 1
fi

echo "==> GET /api/analytics/dashboard"
curl -sf "$API/api/analytics/dashboard" -H "Authorization: Bearer $TOKEN" >/dev/null

echo "e2e_smoke OK (practice create HTTP $CODE)"
