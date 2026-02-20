#!/usr/bin/env pwsh
# FitTrack — One-command local demo (Windows / PowerShell)
# Usage: .\scripts\demo.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "`n=== FitTrack Local Demo ===" -ForegroundColor Cyan

# 1) Start infrastructure
Write-Host "`n[1/4] Starting infrastructure (Oracle + Redis + API)..." -ForegroundColor Yellow
docker compose -f docker/docker-compose.yml up -d
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: docker compose up failed" -ForegroundColor Red; exit 1 }

# 2) Wait for Oracle to be ready (up to 180s)
Write-Host "[2/4] Waiting for Oracle to be ready (up to 180s)..." -ForegroundColor Yellow
$maxWait = 180
$elapsed = 0
$ready = $false
while ($elapsed -lt $maxWait) {
    try {
        python -c "import oracledb; c=oracledb.connect(user='fittrack',password='FitTrack_Dev_2026!',dsn='localhost:1521/FREEPDB1'); c.close()" 2>$null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    } catch {}
    Start-Sleep -Seconds 5
    $elapsed += 5
    Write-Host "  ... waiting ($elapsed s)" -ForegroundColor DarkGray
}
if (-not $ready) {
    Write-Host "WARNING: Oracle may still be starting. Continuing anyway..." -ForegroundColor DarkYellow
}
Write-Host "  Oracle ready!" -ForegroundColor Green

# 3) Migrate + seed
Write-Host "[3/4] Running migrations + seeding data..." -ForegroundColor Yellow
python -c "from scripts.migrations import run_migrations; import oracledb; c=oracledb.connect(user='fittrack',password='FitTrack_Dev_2026!',dsn='localhost:1521/FREEPDB1'); print(run_migrations(c)); c.close()"
python scripts/seed_data.py

# 4) Start API
Write-Host "`n[4/4] Starting API server..." -ForegroundColor Yellow
Write-Host ""
Write-Host "  Swagger UI:  http://localhost:8000/docs" -ForegroundColor Green
Write-Host "  Health:      http://localhost:8000/health" -ForegroundColor Green
Write-Host "  Test page:   http://localhost:8000/test" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C to stop the server." -ForegroundColor DarkGray
Write-Host ""

uvicorn fittrack.main:app --host 0.0.0.0 --port 8000 --reload --app-dir src
