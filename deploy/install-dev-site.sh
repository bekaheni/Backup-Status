#!/usr/bin/env bash
# Install Nginx vhost, TLS cert, and systemd service for backup-status dev.
set -euo pipefail

APP_ROOT="/opt/backup-status-dev"
DOMAIN="backup-d.bekat.co.uk"
NGINX_SITE="backup-status-dev"
CERT_PATH="/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run with sudo: sudo $APP_ROOT/deploy/install-dev-site.sh"
  exit 1
fi

if [[ ! -f "$APP_ROOT/.env" ]]; then
  echo "ERROR: $APP_ROOT/.env not found. Copy from prod or create from .env.example first."
  exit 1
fi

if [[ ! -x "$APP_ROOT/venv/bin/gunicorn" ]]; then
  echo "ERROR: Virtual environment not ready. Run: cd $APP_ROOT && python3 -m venv venv && venv/bin/pip install -r requirements.txt"
  exit 1
fi

echo "==> Installing systemd unit..."
install -m 0644 "$APP_ROOT/deploy/backup-status-dev.service" \
  /etc/systemd/system/backup-status-dev.service
systemctl daemon-reload
systemctl enable backup-status-dev.service
systemctl restart backup-status-dev.service

for _ in 1 2 3 4 5; do
  if [[ -S /run/backup-status-dev/backup-status.sock ]]; then
    break
  fi
  sleep 1
done

if [[ ! -S /run/backup-status-dev/backup-status.sock ]]; then
  echo "ERROR: App socket not created. Check: journalctl -u backup-status-dev -n 50"
  exit 1
fi
echo "App socket OK: /run/backup-status-dev/backup-status.sock"

echo "==> Installing Nginx site..."
mkdir -p /var/www/certbot

if [[ ! -f "$CERT_PATH" ]]; then
  echo "No TLS cert yet — installing HTTP-only vhost for Certbot..."
  install -m 0644 "$APP_ROOT/deploy/nginx/backup-status-dev-http-only.conf" \
    "/etc/nginx/sites-available/${NGINX_SITE}"
  ln -sf "/etc/nginx/sites-available/${NGINX_SITE}" "/etc/nginx/sites-enabled/${NGINX_SITE}"
  nginx -t
  systemctl reload nginx
  echo "==> Requesting certificate..."
  certbot certonly --webroot -w /var/www/certbot \
    -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email
fi

install -m 0644 "$APP_ROOT/deploy/nginx/backup-status-dev.conf" \
  "/etc/nginx/sites-available/${NGINX_SITE}"
ln -sf "/etc/nginx/sites-available/${NGINX_SITE}" "/etc/nginx/sites-enabled/${NGINX_SITE}"

nginx -t
systemctl reload nginx

echo ""
echo "Done. Open: https://${DOMAIN}/"
echo "Service: systemctl status backup-status-dev"
