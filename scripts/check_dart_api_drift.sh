#!/usr/bin/env bash
# Lightweight FR-CLIENT-04 drift guard: ensure the hand-maintained Dart client
# still covers learner routes present in openapi/openapi.json.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OPENAPI="$ROOT/openapi/openapi.json"
CLIENT="$ROOT/mobile/packages/cissp_api/lib/src/client.dart"

missing=0
check() {
  local needle="$1"
  local file="$2"
  if ! grep -q "$needle" "$file"; then
    echo "MISSING in $file: $needle" >&2
    missing=1
  fi
}

check '/api/practice/sessions' "$OPENAPI"
check '/api/exam/sessions' "$OPENAPI"
check '/api/analytics/weak-areas' "$OPENAPI"
check '/api/users/me/preferences' "$OPENAPI"

check "createPractice" "$CLIENT"
check "examNext" "$CLIENT"
check "weakAreas" "$CLIENT"
check "putPreferences" "$CLIENT"
check "books" "$CLIENT"
check "chapters" "$CLIENT"

if [[ "$missing" -ne 0 ]]; then
  echo "Dart API drift check failed." >&2
  exit 1
fi
echo "Dart API drift check OK."
