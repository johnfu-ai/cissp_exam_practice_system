#!/bin/sh
# Tier 2 #25: dump the Postgres DB to the `backups` volume via the compose
# `backup` service (keeps the 30 most recent gzipped dumps).
#
# For daily backups (PRD §7.3), run this from a host crontab, e.g.:
#   7 2 * * *  cd /opt/cissp_exam && ./scripts/backup.sh >> /var/log/cissp-backup.log 2>&1
set -e
cd "$(dirname "$0")/.."
exec docker compose --profile backup run --rm backup
