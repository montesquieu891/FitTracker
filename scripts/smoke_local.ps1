# =============================================================================
# FitTrack — Local smoke test (PowerShell)
# Verifies that Docker infrastructure and API are healthy.
#
# Usage:
#   .\scripts\smoke_local.ps1
#
# Prerequisites:
#   - Docker containers running (make docker-up)
#   - API running on localhost:8000 (make dev OR docker api service)
# =============================================================================

$ErrorActionPreference = "Continue"

$ApiBase = if ($env:API_BASE) { $env:API_BASE } else { "http://localhost:8000" }
$Timeout = 10

$pass = 0; $fail = 0; $warn = 0

function Write-Pass($msg) { $script:pass++; Write-Host "  [PASS] $msg" -ForegroundColor Green }
function Write-Fail($msg) { $script:fail++; Write-Host "  [FAIL] $msg" -ForegroundColor Red }
function Write-Warn($msg) { $script:warn++; Write-Host "  [WARN] $msg" -ForegroundColor Yellow }

Write-Host "============================================"
Write-Host " FitTrack Local Smoke Test"
Write-Host "============================================"
Write-Host ""

# ── 1. Docker containers ─────────────────────────────────────────────────────
Write-Host "1) Docker containers"

function Test-Container($name) {
    try {
        $status = (docker inspect --format='{{.State.Health.Status}}' $name 2>$null)
        if ($status -eq "healthy") { Write-Pass "$name is healthy" }
        elseif ($status -match "running|starting") { Write-Warn "$name is $status (not yet healthy)" }
        else { Write-Fail "${name}: status=$status" }
    }
    catch {
        Write-Fail "${name}: not found"
    }
}

Test-Container "fittrack-oracle"
Test-Container "fittrack-redis"

# Redis ping
try {
    $pong = docker exec fittrack-redis redis-cli ping 2>$null
    if ($pong -match "PONG") { Write-Pass "Redis PING -> PONG" }
    else { Write-Fail "Redis PING failed" }
}
catch { Write-Fail "Redis PING failed: $_" }

Write-Host ""

# ── 2. API Health endpoints ───────────────────────────────────────────────────
Write-Host "2) API Health endpoints"

function Test-Endpoint($path, $desc, $expectField) {
    try {
        $response = Invoke-WebRequest -Uri "$ApiBase$path" -TimeoutSec $Timeout -UseBasicParsing -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            if ($expectField -and ($response.Content -notmatch $expectField)) {
                Write-Warn "$desc -> 200 but missing '$expectField'"
            }
            else {
                Write-Pass "$desc -> 200"
            }
        }
        else {
            Write-Fail "$desc -> HTTP $($response.StatusCode)"
        }
    }
    catch {
        $code = $_.Exception.Response.StatusCode.value__
        if ($code) { Write-Fail "$desc -> HTTP $code" }
        else { Write-Fail "$desc -> connection refused (API not running?)" }
    }
}

Test-Endpoint "/health"       "GET /health"       "status"
Test-Endpoint "/health/live"  "GET /health/live"   "alive"
Test-Endpoint "/health/ready" "GET /health/ready"  "ready"

Write-Host ""

# ── 3. Swagger / OpenAPI ──────────────────────────────────────────────────────
Write-Host "3) Swagger / OpenAPI"

Test-Endpoint "/docs"         "GET /docs (Swagger UI)"  "swagger"
Test-Endpoint "/openapi.json" "GET /openapi.json"       "paths"

Write-Host ""

# ── 4. Route count ───────────────────────────────────────────────────────────
Write-Host "4) Route count"
try {
    $openapi = Invoke-RestMethod -Uri "$ApiBase/openapi.json" -TimeoutSec $Timeout
    $count = $openapi.paths.PSObject.Properties.Name.Count
    if ($count -gt 50) { Write-Pass "$count API paths registered" }
    elseif ($count -gt 0) { Write-Warn "$count API paths (expected ~76)" }
    else { Write-Fail "No API paths found" }
}
catch { Write-Fail "Could not read API routes" }

Write-Host ""

# ── Summary ──────────────────────────────────────────────────────────────────
Write-Host "============================================"
Write-Host " Results: $pass passed, $warn warnings, $fail failed"
Write-Host "============================================"

if ($fail -gt 0) { exit 1 }
exit 0
