#!/usr/bin/env pwsh
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$BASE_URL = $env:BASE_URL
if (-not $BASE_URL -or $BASE_URL -eq '') { $BASE_URL = 'http://localhost:8000' }
$RETRIES = if ($env:RETRIES) { [int]$env:RETRIES } else { 24 }
$SLEEP_SECONDS = if ($env:SLEEP_SECONDS) { [int]$env:SLEEP_SECONDS } else { 5 }
$TIMEOUT = if ($env:TIMEOUT) { [int]$env:TIMEOUT } else { 5 }
$CHECK_DOCS = if ($env:CHECK_DOCS) { [int]$env:CHECK_DOCS } else { 0 }

function Log([string]$msg) { Write-Host "[smoke] $msg" }

function CheckEndpoint([string]$path, [int]$expect) {
    for ($i = 1; $i -le $RETRIES; $i++) {
        try {
            $response = Invoke-WebRequest -Uri "$BASE_URL$path" -Method GET -TimeoutSec $TIMEOUT -UseBasicParsing
            if ($response.StatusCode -eq $expect) {
                Log "PASS $path -> $($response.StatusCode) (attempt $i)"
                return $true
            }
            Log "WARN $path -> $($response.StatusCode) (attempt $i/$RETRIES)"
        } catch {
            Log "WARN $path failed: $($_.Exception.Message) (attempt $i/$RETRIES)"
        }
        Start-Sleep -Seconds $SLEEP_SECONDS
    }
    Log "FAIL $path did not return $expect after $RETRIES attempts"
    return $false
}

Log "BASE_URL=$BASE_URL"
$ok = $true
$ok = CheckEndpoint '/health' 200 -and $ok
$ok = CheckEndpoint '/health/live' 200 -and $ok
$ok = CheckEndpoint '/health/ready' 200 -and $ok

if ($CHECK_DOCS -eq 1) {
    $ok = CheckEndpoint '/docs' 200 -and $ok
} else {
    Log "SKIP /docs (set CHECK_DOCS=1 to include)"
}

if (-not $ok) { exit 1 }
Log "All required smoke checks passed."
