# ============================================================
# 串口网桥后台启动脚本 (部署版)
# ============================================================
# 用法: 右键 -> 使用 PowerShell 运行
# 或者: powershell -ExecutionPolicy Bypass -File start_serial_bridge.ps1
# ============================================================

$SERIAL_PORT = "COM1"
$BAUDRATE = 19200
$TCP_PORT = 7777
$LOG_DIR = "$PSScriptRoot\logs"
$LOG_FILE = "$LOG_DIR\serial_bridge.log"
$PID_FILE = "$LOG_DIR\serial_bridge.pid"

# 创建日志目录
if (-not (Test-Path $LOG_DIR)) {
    New-Item -ItemType Directory -Path $LOG_DIR -Force | Out-Null
}

# 检查是否已经在运行
$existingProcess = Get-WmiObject Win32_Process | 
    Where-Object { $_.CommandLine -like "*tcp_serial_redirect*" }

if ($existingProcess) {
    Write-Host "⚠️ 串口网桥已在运行 (PID: $($existingProcess.ProcessId))" -ForegroundColor Yellow
    Write-Host "   如需重启，请先运行: .\stop_serial_bridge.ps1"
    exit 0
}

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "   🔥 启动串口网桥 (后台模式)" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "   物理串口: $SERIAL_PORT @ $BAUDRATE"
Write-Host "   转发地址: 0.0.0.0:$TCP_PORT"
Write-Host "   Docker内: socket://host.docker.internal:$TCP_PORT"
Write-Host "   日志文件: $LOG_FILE"
Write-Host "========================================================" -ForegroundColor Cyan

# 后台启动
$process = Start-Process -FilePath "python" `
    -ArgumentList "-m", "serial.tools.tcp_serial_redirect", "-P", $TCP_PORT, $SERIAL_PORT, $BAUDRATE `
    -WindowStyle Hidden `
    -PassThru `
    -RedirectStandardOutput $LOG_FILE `
    -RedirectStandardError "$LOG_FILE.err"

if ($process) {
    Write-Host ""
    Write-Host "✅ 串口网桥已在后台启动!" -ForegroundColor Green
    Write-Host "   PID: $($process.Id)"
    Write-Host ""
    Write-Host "📋 常用命令:" -ForegroundColor Yellow
    Write-Host "   查看状态: .\check_serial_bridge.ps1"
    Write-Host "   查看日志: Get-Content $LOG_FILE -Tail 20"
    Write-Host "   停止服务: .\stop_serial_bridge.ps1"
    Write-Host ""
    
    # 保存 PID
    $process.Id | Out-File $PID_FILE -Force
} else {
    Write-Host "❌ 启动失败!" -ForegroundColor Red
    exit 1
}
