# ============================================================
# Furnace Backend v1.1.8 - Stop Script
# ============================================================

Write-Host "============================================" -ForegroundColor Cyan
Write-Host " Furnace Backend - Stopping Service" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# Find and stop Python backend process by port
$netstat = netstat -ano | Select-String ":8082.*LISTENING"
if ($netstat) {
    $pids = $netstat | ForEach-Object {
        ($_ -split '\s+')[-1]
    } | Sort-Object -Unique
    
    foreach ($pid in $pids) {
        if ($pid -match '^\d+$' -and $pid -ne "0") {
            Write-Host "Stopping process PID: $pid" -ForegroundColor Yellow
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Host "[OK] Backend service stopped" -ForegroundColor Green
} else {
    Write-Host "[INFO] No backend service running on port 8082" -ForegroundColor Gray
}
