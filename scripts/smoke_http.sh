#!/usr/bin/env bash
set -euo pipefail

BASE_URL=${BASE_URL:-http://localhost:8000}
RETRIES=${RETRIES:-24}
SLEEP_SECONDS=${SLEEP_SECONDS:-5}
TIMEOUT=${TIMEOUT:-5}
CHECK_DOCS=${CHECK_DOCS:-0}

log() { printf '%s %s\n' "[smoke]" "$*"; }

check_endpoint() {
  local path=$1
  local expect=$2
  local attempt=1
  while [ $attempt -le $RETRIES ]; do
    if response=$(curl -sS -m "$TIMEOUT" -o /dev/null -w "%{http_code}" "${BASE_URL}${path}"); then
      if [ "$response" = "$expect" ]; then
        log "PASS ${path} -> ${response} (attempt ${attempt})"
        return 0
      fi
      log "WARN ${path} -> ${response} (attempt ${attempt}/${RETRIES})"
    else
      log "WARN ${path} curl failed (attempt ${attempt}/${RETRIES})"
    fi
    attempt=$((attempt + 1))
    sleep "$SLEEP_SECONDS"
  done
  log "FAIL ${path} did not return ${expect} after ${RETRIES} attempts"
  return 1
}

main() {
  log "BASE_URL=${BASE_URL}"
  check_endpoint /health 200
  check_endpoint /health/live 200
  check_endpoint /health/ready 200

  if [ "$CHECK_DOCS" = "1" ]; then
    check_endpoint /docs 200
  else
    log "SKIP /docs (set CHECK_DOCS=1 to include)"
  fi

  log "All required smoke checks passed."
}

main "$@"
