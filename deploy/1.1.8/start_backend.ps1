# ============================================================
# Furnace Backend v1.1.8 - Start Script
# ============================================================

$ErrorActionPreference = "Stop"
$INSTALL_DIR = "D:\furnace-backend"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host " Furnace Backend - Starting Service" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# Check install directory
if (-not (Test-Path $INSTALL_DIR)) {
    Write-Host "[ERROR] Install directory not found: $INSTALL_DIR" -ForegroundColor Red
    Write-Host "   Please run install.ps1 first" -ForegroundColor Gray
    exit 1
}

Set-Location $INSTALL_DIR

# Check venv
if (-not (Test-Path "venv\Scripts\python.exe")) {
    Write-Host "[ERROR] Virtual environment not found. Run install.ps1 first" -ForegroundColor Red
    exit 1
}

# Check InfluxDB
Write-Host "`nChecking InfluxDB..." -ForegroundColor Yellow
$influxRunning = docker ps --filter "name=furnace-influxdb" --format "{{.Names}}" 2>$null
if ($influxRunning -eq "furnace-influxdb") {
    Write-Host "[OK] InfluxDB is running" -ForegroundColor Green
} else {
    Write-Host "[WARN] InfluxDB not running, starting..." -ForegroundColor Yellow
    if (Test-Path "docker-compose-influxdb.yml") {
        docker compose -f docker-compose-influxdb.yml up -d
    }
}

# Start backend
Write-Host "`nStarting backend service..." -ForegroundColor Yellow
Write-Host "URL: http://localhost:8082" -ForegroundColor Cyan
Write-Host "Health: http://localhost:8082/health" -ForegroundColor Cyan
Write-Host "API Docs: http://localhost:8082/docs" -ForegroundColor Cyan
Write-Host "`nPress Ctrl+C to stop" -ForegroundColor Gray
Write-Host "============================================`n" -ForegroundColor Cyan

& "$INSTALL_DIR\venv\Scripts\python.exe" main.py
