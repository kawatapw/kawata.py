#!/bin/bash
# ci-bootstrap.sh - Bootstrap timing for CI workflows

set -e

# Create state directory
mkdir -p .ci/state

# Record bootstrap timestamp
BOOTSTRAP_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Build bootstrap state
cat > .ci/state/bootstrap.json << EOF
{
  "bootstrap_time": "$BOOTSTRAP_TIME",
  "workflow": "${GITHUB_WORKFLOW:-unknown}",
  "job": "${GITHUB_JOB:-unknown}",
  "run_id": "${GITHUB_RUN_ID:-unknown}",
  "run_number": "${GITHUB_RUN_NUMBER:-unknown}",
  "commit": "${GITHUB_SHA:-unknown}",
  "repository": "${GITHUB_REPOSITORY:-unknown}",
  "actor": "${GITHUB_ACTOR:-unknown}",
  "ref": "${GITHUB_REF:-unknown}",
  "event": "${GITHUB_EVENT_NAME:-unknown}",
  "runner": "${RUNNER_NAME:-unknown}",
  "os": "$(uname -s) $(uname -r)"
}
EOF

echo "Bootstrap complete at $BOOTSTRAP_TIME"
