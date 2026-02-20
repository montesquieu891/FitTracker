#!/usr/bin/env bash
# =============================================================================
# FitTrack — Local smoke test
# Verifies that Docker infrastructure and API are healthy.
#
# Usage:
#   bash scripts/smoke_local.sh
#
# Prerequisites:
#   - Docker containers running (make docker-up)
#   - API running on localhost:8000 (make dev OR docker api service)
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS=0
FAIL=0
WARN=0

pass()  { ((PASS++)); echo -e "  ${GREEN}✓${NC} $1"; }
fail()  { ((FAIL++)); echo -e "  ${RED}✗${NC} $1"; }
warn()  { ((WARN++)); echo -e "  ${YELLOW}!${NC} $1"; }

API_BASE="${API_BASE:-http://localhost:8000}"
TIMEOUT="${TIMEOUT:-10}"
DOCKER_COMPOSE="docker compose -f docker/docker-compose.yml"

echo "============================================"
echo " FitTrack Local Smoke Test"
echo "============================================"
echo ""

# ── 1. Docker containers ─────────────────────────────────────────────────────
echo "1) Docker containers"

check_container() {
    local name="$1"
    local status
    status=$(docker inspect --format='{{.State.Health.Status}}' "$name" 2>/dev/null || echo "not_found")
    if [ "$status" = "healthy" ]; then
        pass "$name is healthy"
    elif [ "$status" = "running" ] || [ "$status" = "starting" ]; then
        warn "$name is $status (not yet healthy)"
    else
        fail "$name: status=$status"
    fi
}

check_container "fittrack-oracle"
check_container "fittrack-redis"

# Quick Redis ping
if docker exec fittrack-redis redis-cli ping 2>/dev/null | grep -q "PONG"; then
    pass "Redis PING → PONG"
else
    fail "Redis PING failed"
fi

echo ""

# ── 2. API Health endpoints ───────────────────────────────────────────────────
echo "2) API Health endpoints"

check_endpoint() {
    local path="$1"
    local desc="$2"
    local expect_field="${3:-}"
    local http_code
    local body

    http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" "${API_BASE}${path}" 2>/dev/null || echo "000")

    if [ "$http_code" = "200" ]; then
        if [ -n "$expect_field" ]; then
            body=$(curl -s --max-time "$TIMEOUT" "${API_BASE}${path}" 2>/dev/null)
            if echo "$body" | grep -q "$expect_field"; then
                pass "$desc → 200 (contains '$expect_field')"
            else
                warn "$desc → 200 but missing '$expect_field'"
            fi
        else
            pass "$desc → 200"
        fi
    elif [ "$http_code" = "000" ]; then
        fail "$desc → connection refused (API not running?)"
    else
        fail "$desc → HTTP $http_code"
    fi
}

check_endpoint "/health"       "GET /health"       '"status"'
check_endpoint "/health/live"  "GET /health/live"   '"alive"'
check_endpoint "/health/ready" "GET /health/ready"  '"ready"'

echo ""

# ── 3. Swagger / OpenAPI ──────────────────────────────────────────────────────
echo "3) Swagger / OpenAPI"

check_endpoint "/docs"         "GET /docs (Swagger UI)"   "swagger"
check_endpoint "/openapi.json" "GET /openapi.json"        '"paths"'

echo ""

# ── 4. API routes count ──────────────────────────────────────────────────────
echo "4) Route count"
route_count=$(curl -s --max-time "$TIMEOUT" "${API_BASE}/openapi.json" 2>/dev/null | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('paths',{})))" 2>/dev/null || echo "0")
if [ "$route_count" -gt 50 ]; then
    pass "$route_count API paths registered"
elif [ "$route_count" -gt 0 ]; then
    warn "$route_count API paths (expected ~76)"
else
    fail "Could not read API routes"
fi

echo ""

# ── Summary ──────────────────────────────────────────────────────────────────
echo "============================================"
echo -e " Results: ${GREEN}${PASS} passed${NC}, ${YELLOW}${WARN} warnings${NC}, ${RED}${FAIL} failed${NC}"
echo "============================================"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
exit 0
