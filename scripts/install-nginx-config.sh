#!/usr/bin/env bash
set -euo pipefail

echo "Sourcing environment from .env file"
while IFS= read -r line || [[ -n "$line" ]]; do
  if [[ "$line" =~ ^[[:space:]]*# || -z "$line" ]]; then
    continue
  fi
  key="${line%%=*}"
  value="${line#*=}"
  export "$key"="$value"
done < .env

echo "Installing nginx configuration"
sed -e "s|\${APP_PORT}|$APP_PORT|g" \
    -e "s|\${DOMAIN}|$DOMAIN|g" \
    -e "s|\${SSL_CERT_PATH}|$SSL_CERT_PATH|g" \
    -e "s|\${SSL_KEY_PATH}|$SSL_KEY_PATH|g" \
    -e "s|\${DATA_DIRECTORY}|$DATA_DIRECTORY|g" \
    ext/nginx.conf.example > /etc/nginx/sites-available/bancho.conf

ln -f -s /etc/nginx/sites-available/bancho.conf /etc/nginx/sites-enabled/bancho.conf

echo "Restarting nginx"
service nginx restart

echo "Nginx configuration installed"