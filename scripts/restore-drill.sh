#!/bin/sh
# Restore drill (item #7): prove the newest backup actually restores.
#
# Restores the latest (or a given) backup into a THROWAWAY database inside
# the running postgres container, verifies the core tables + data exist,
# then drops the throwaway DB. Never touches the live database.
#
# Usage:  ./scripts/restore-drill.sh [backup-file]
#
# A backup is only real once a restore has been exercised — run this after
# every backup-infra change and at least monthly, e.g. from cron:
#   17 3 1 * *  cd /opt/cissp_exam && ./scripts/restore-drill.sh >> /var/log/cissp-drill.log 2>&1
set -e
cd "$(dirname "$0")/.."

# The backup service declares entrypoint ["/bin/sh","-c"] + an inline command,
# so any `compose run` override must reset the entrypoint or the args are
# silently swallowed (/bin/sh -c sh ...). --entrypoint /bin/sh + `-c <body>`
# is the reliable shape. The drill body lives in a quoted heredoc so its own
# single quotes never fight the shell.
run_in_backup() {
  docker compose --profile backup run --rm --no-deps --entrypoint /bin/sh \
    -e DRILL_DB -e FILE backup -c "$1"
}

FILE="${1:-}"
if [ -z "$FILE" ]; then
  FILE=$(run_in_backup \
    "ls -1t /backups/cissp-*.dump /backups/cissp-*.sql.gz 2>/dev/null | head -1" | tail -1)
  FILE="${FILE#/backups/}"
  if [ -z "$FILE" ]; then
    echo "DRILL FAILED: no backups found in the backups volume (run ./scripts/backup.sh first)" >&2
    exit 1
  fi
  echo "drilling against latest backup: $FILE"
fi

DRILL_DB="cissp_drill_$(date -u +%Y%m%d%H%M%S)"

DRILL_BODY=$(cat <<'EOS'
set -e
createdb "$DRILL_DB"
case "$FILE" in
  *.dump)    pg_restore --no-owner --exit-on-error --dbname="$DRILL_DB" "/backups/$FILE" ;;
  *.sql.gz)  gunzip -c "/backups/$FILE" | psql -v ON_ERROR_STOP=1 -d "$DRILL_DB" ;;
  *)         echo "DRILL FAILED: unrecognized backup format: $FILE"; exit 2 ;;
esac
for t in users questions question_translations exam_sessions practice_sessions alembic_version; do
  # \dt + whole-word grep: quote-free table check (psql -c does not perform
  # :'var' interpolation in this image, and shell quotes cannot nest here).
  psql -d "$DRILL_DB" -tAc "\dt" | grep -qw "$t" \
    || { echo "DRILL FAILED: table $t missing after restore"; exit 3; }
done
n=$(psql -d "$DRILL_DB" -tAc "SELECT count(*) FROM users")
[ "$n" -ge 1 ] || { echo "DRILL FAILED: restored dump has no users"; exit 4; }
v=$(psql -d "$DRILL_DB" -tAc "SELECT version_num FROM alembic_version")
echo "DRILL PASSED: $FILE restored into $DRILL_DB"
echo "  core tables present, $n users, alembic at $v"
EOS
)

# Cleanup safety net: drop the throwaway DB even if a check fails.
cleanup() {
  docker compose --profile backup run --rm --no-deps --entrypoint /bin/sh \
    backup -c "dropdb --if-exists '$DRILL_DB'" >/dev/null 2>&1 || true
}
trap cleanup EXIT

export DRILL_DB FILE
run_in_backup "$DRILL_BODY"
