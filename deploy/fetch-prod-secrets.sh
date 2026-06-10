#!/usr/bin/env bash
# Copy .env and optional database from production backup-status server.
set -euo pipefail

APP_ROOT="/opt/backup-status-dev"
PROD_HOST="${PROD_HOST:-57.128.159.201}"
PROD_PORT="${PROD_PORT:-56765}"
PROD_USER="${PROD_USER:-ubuntu}"
PROD_PATH="${PROD_PATH:-/opt/backup-status}"

SCP=(scp -P "$PROD_PORT")
SSH=(ssh -p "$PROD_PORT")

echo "Copying .env from ${PROD_USER}@${PROD_HOST}:${PROD_PATH}/.env ..."
"${SCP[@]}" "${PROD_USER}@${PROD_HOST}:${PROD_PATH}/.env" "$APP_ROOT/.env"
chmod 600 "$APP_ROOT/.env"

read -r -p "Also copy production SQLite database? (y/n): " COPY_DB
if [[ "$COPY_DB" == "y" ]]; then
  for db_path in "$PROD_PATH/backup_status.db" "$PROD_PATH/instance/backup_status.db"; do
    if "${SSH[@]}" "${PROD_USER}@${PROD_HOST}" "test -f '$db_path'"; then
      echo "Copying $db_path ..."
      "${SCP[@]}" "${PROD_USER}@${PROD_HOST}:${db_path}" "$APP_ROOT/backup_status.db"
      break
    fi
  done
fi

echo "Done. Review $APP_ROOT/.env and run: sudo $APP_ROOT/deploy/install-dev-site.sh"
