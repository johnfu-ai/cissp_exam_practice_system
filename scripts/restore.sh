#!/bin/sh
# Tier 2 #25: restore a gzipped dump from the `backups` volume.
#
# Usage:   ./scripts/restore.sh <backup-file>   e.g. cissp-20260720T020000Z.sql.gz
#
# WARNING: this OVERWRITES the current database. Stop the backend first:
#   docker compose stop backend migrate
# then optionally drop/recreate the DB for a clean restore:
#   docker compose exec postgres dropdb -U cissp cissp
#   docker compose exec postgres createdb -U cissp cissp
# then run migrations before restarting the backend:
#   docker compose run --rm migrate
set -e

FILE="$1"
if [ -z "$FILE" ]; then
  echo "Usage: $0 <backup-file-name> (e.g. cissp-20260720T020000Z.sql.gz)" >&2
  exit 1
fi

cd "$(dirname "$0")/.."
# The `backup` service image has psql + the backups volume + PG* env, so reuse it
# to stream the gunzipped dump into the database.
exec docker compose run --rm --no-deps backup sh -c \
  "gunzip -c '/backups/${FILE}' | psql -v ON_ERROR_STOP=1"
