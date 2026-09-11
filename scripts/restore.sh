#!/bin/sh
# Tier 2 #25: restore a backup from the `backups` volume.
#
# Usage:   ./scripts/restore.sh <backup-file>
#          e.g. cissp-20260911T020000Z.dump        (custom format, current)
#          or  cissp-20260720T020000Z.sql.gz       (legacy plain+gzip)
#
# WARNING: this OVERWRITES the current database. Stop the backend first:
#   docker compose stop backend migrate
# then optionally drop/recreate the DB for a clean restore:
#   docker compose exec postgres dropdb -U cissp cissp
#   docker compose exec postgres createdb -U cissp cissp
# then run migrations before restarting the backend:
#   docker compose run --rm migrate
#
# Practice the procedure safely first with scripts/restore-drill.sh (restores
# into a throwaway database, verifies, and drops it).
set -e

FILE="$1"
if [ -z "$FILE" ]; then
  echo "Usage: $0 <backup-file-name> (e.g. cissp-20260911T020000Z.dump)" >&2
  exit 1
fi

case "$FILE" in
  *.dump)
    # Custom format: pg_restore handles clean + errors natively.
    INNER="pg_restore --no-owner --exit-on-error --dbname=\$PGDATABASE '/backups/$FILE'"
    ;;
  *.sql.gz)
    INNER="gunzip -c '/backups/$FILE' | psql -v ON_ERROR_STOP=1"
    ;;
  *)
    echo "Unrecognized backup format: $FILE (expected .dump or .sql.gz)" >&2
    exit 2
    ;;
esac

cd "$(dirname "$0")/.."
# The `backup` service image has psql/pg_restore + the backups volume + PG*
# env, so reuse it to apply the dump. The service entrypoint is
# ["/bin/sh","-c"], so the entrypoint must be reset for the run override to
# take effect (otherwise /bin/sh -c sh ... silently does nothing).
exec docker compose --profile backup run --rm --no-deps --entrypoint /bin/sh \
  backup -c "$INNER"
