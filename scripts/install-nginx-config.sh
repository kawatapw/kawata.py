#!/usr/bin/env bash
set -euo pipefail

if [[ -f .env ]]; then
  echo "Sourcing environment from .env file"
  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" =~ ^[[:space:]]*# || -z "$line" ]]; then
      continue
    fi
    key="${line%%=*}"
    value="${line#*=}"
    export "$key"="$value"
  done < .env
else
  echo "No .env file found, using environment variables passed to the container"
fi

if [[ ! -f "$SSL_CERT_PATH" || ! -f "$SSL_KEY_PATH" ]]; then
  echo "SSL certs missing; generating self-signed certs for tests"
  mkdir -p "$(dirname "$SSL_CERT_PATH")"
  openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout "$SSL_KEY_PATH" -out "$SSL_CERT_PATH" -subj "/CN=localhost"
fi

echo "Installing nginx configuration"
sed -e "s|\${APP_PORT}|$APP_PORT|g" \
    -e "s|\${DOMAIN}|$DOMAIN|g" \
    -e "s|\${SSL_CERT_PATH}|$SSL_CERT_PATH|g" \
    -e "s|\${SSL_KEY_PATH}|$SSL_KEY_PATH|g" \
    -e "s|\${DATA_DIRECTORY}|$DATA_DIRECTORY|g" \
    ext/nginx.conf.example > /etc/nginx/sites-available/bancho.conf

ln -f -s /etc/nginx/sites-available/bancho.conf /etc/nginx/sites-enabled/bancho.conf

echo "Restarting nginx"
if service nginx restart; then
    echo "Nginx restarted successfully"
else
    echo "Failed to restart nginx. Status:"
    nginx
fi

echo "Nginx configuration installed"