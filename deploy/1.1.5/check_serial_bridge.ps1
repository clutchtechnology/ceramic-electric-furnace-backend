# ============================================================
# 查看串口网桥状态脚本
# ============================================================

$LOG_DIR = "$PSScriptRoot\logs"
$PID_FILE = "$LOG_DIR\serial_bridge.pid"
$LOG_FILE = "$LOG_DIR\serial_bridge.log"
$TCP_PORT = 7777

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "   📊 串口网桥状态" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# 检查进程
$running = $false
if (Test-Path $PID_FILE) {
    $savedPid = Get-Content $PID_FILE
    try {
        $process = Get-Process -Id $savedPid -ErrorAction Stop
        Write-Host "✅ 状态: 运行中" -ForegroundColor Green
        Write-Host "   PID: $savedPid"
        Write-Host "   内存: $([math]::Round($process.WorkingSet64 / 1MB, 2)) MB"
        Write-Host "   启动: $($process.StartTime)"
        $running = $true
    } catch {
        Write-Host "❌ 状态: 已停止" -ForegroundColor Red
    }
} else {
    Write-Host "❌ 状态: 未运行" -ForegroundColor Red
}

# 检查端口
Write-Host ""
Write-Host "🔌 端口 $TCP_PORT :" -ForegroundColor Yellow
$listening = netstat -an | Select-String ":$TCP_PORT " | Select-String "LISTENING"
if ($listening) {
    Write-Host "   ✅ 正在监听" -ForegroundColor Green
} else {
    Write-Host "   ❌ 未监听" -ForegroundColor Red
}

# 显示日志
if ((Test-Path $LOG_FILE) -and $running) {
    Write-Host ""
    Write-Host "📋 最近日志:" -ForegroundColor Yellow
    Get-Content $LOG_FILE -Tail 5 -ErrorAction SilentlyContinue
}

Write-Host "========================================================" -ForegroundColor Cyan
