#!/usr/bin/env bash
set -euxo pipefail
# Ensure Nginx Config is Set
scripts/install-nginx-config.sh

# Checking MySQL TCP connection
scripts/wait-for-it.sh --timeout=60 $DB_HOST:$DB_PORT

# Checking Redis connection
scripts/wait-for-it.sh --timeout=60 $REDIS_HOST:$REDIS_PORT

python3.11 main.py
