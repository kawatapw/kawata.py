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

echo "Checking and creating log directories and files"
# Extract log paths from nginx config example and create them if they don't exist
NGINX_CONFIG_EXAMPLE="ext/nginx.conf.example"

if [[ -f "$NGINX_CONFIG_EXAMPLE" ]]; then
  # Extract all access_log and error_log paths from the nginx config
  LOG_PATHS=$(grep -E "^\s*(access_log|error_log)" "$NGINX_CONFIG_EXAMPLE" | \
    sed -E 's/^\s*(access_log|error_log)\s+//' | \
    sed -E 's/;.*$//' | \
    sed -E "s|\$\{DOMAIN\}|$DOMAIN|g" | \
    sed -E "s|\$\{DATA_DIRECTORY\}|$DATA_DIRECTORY|g")

  if [[ -z "$LOG_PATHS" ]]; then
    echo "Warning: No log paths found in $NGINX_CONFIG_EXAMPLE"
  else
    echo "Found log paths in nginx config:"
    echo "$LOG_PATHS"
    
    # Create each log file if it doesn't exist
    while IFS= read -r log_path; do
      if [[ -n "$log_path" ]]; then
        if [[ ! -f "$log_path" ]]; then
          echo "Creating log file: $log_path"
          mkdir -p "$(dirname "$log_path")"
          touch "$log_path"
        else
          echo "Log file already exists: $log_path"
        fi
      fi
    done <<< "$LOG_PATHS"
  fi
else
  echo "Warning: nginx config example file not found at $NGINX_CONFIG_EXAMPLE"
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