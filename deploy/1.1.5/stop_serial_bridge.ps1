# ============================================================
# 停止串口网桥脚本
# ============================================================

$LOG_DIR = "$PSScriptRoot\logs"
$PID_FILE = "$LOG_DIR\serial_bridge.pid"

Write-Host "🛑 停止串口网桥..." -ForegroundColor Yellow

# 方法1: 通过 PID 文件停止
if (Test-Path $PID_FILE) {
    $savedPid = Get-Content $PID_FILE
    try {
        $process = Get-Process -Id $savedPid -ErrorAction Stop
        Stop-Process -Id $savedPid -Force
        Write-Host "✅ 已停止进程 (PID: $savedPid)" -ForegroundColor Green
        Remove-Item $PID_FILE -Force
    } catch {
        Write-Host "⚠️ PID $savedPid 进程不存在" -ForegroundColor Yellow
        Remove-Item $PID_FILE -Force
    }
}

# 方法2: 查找并停止所有相关进程
$processes = Get-WmiObject Win32_Process | 
    Where-Object { $_.CommandLine -like "*tcp_serial_redirect*" }

if ($processes) {
    foreach ($proc in $processes) {
        Write-Host "   停止进程: $($proc.ProcessId)"
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Write-Host "✅ 所有串口网桥进程已停止" -ForegroundColor Green
} elseif (-not (Test-Path $PID_FILE)) {
    Write-Host "ℹ️ 没有运行中的串口网桥进程" -ForegroundColor Cyan
}
