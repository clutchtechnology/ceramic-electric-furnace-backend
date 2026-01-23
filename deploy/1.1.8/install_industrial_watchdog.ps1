<#
.SYNOPSIS
    工控机综合看门狗一键安装脚本
.DESCRIPTION
    从 deploy 目录复制看门狗脚本并配置开机自启动
.USAGE
    cd D:\deploy\1.1.8
    .\install_industrial_watchdog.ps1
#>

param(
    [string]$BackendPath = "D:\furnace-backend",
    [string]$FlutterAppPath = "D:\app\ceramic_electric_furnace.exe",
    [switch]$InstallOnly
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "工控机综合看门狗安装程序 v4.0" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "配置信息:" -ForegroundColor Yellow
Write-Host "  后端路径: $BackendPath" -ForegroundColor White
Write-Host "  Flutter App: $FlutterAppPath" -ForegroundColor White
Write-Host ""

# 提取 Flutter App 进程名（不含.exe）
$FlutterAppName = if (Test-Path $FlutterAppPath) {
    (Get-Item $FlutterAppPath).BaseName
} else {
    "ceramic_electric_furnace"
    Write-Host "警告: Flutter App 路径不存在，使用默认进程名" -ForegroundColor Yellow
}

# 1. 创建看门狗目录
$WatchdogDir = "D:\deploy\watchdog"
if (-not (Test-Path $WatchdogDir)) {
    Write-Host "创建看门狗目录: $WatchdogDir" -ForegroundColor Yellow
    New-Item -Path $WatchdogDir -ItemType Directory -Force | Out-Null
}

# 2. 查找源脚本文件
$SourceScript = $null
$PossiblePaths = @(
    (Join-Path $PSScriptRoot "..\industrial_watchdog.ps1"),
    ".\industrial_watchdog.ps1",
    "..\industrial_watchdog.ps1"
)

foreach ($Path in $PossiblePaths) {
    if (Test-Path $Path) {
        $SourceScript = Resolve-Path $Path
        break
    }
}

if (-not $SourceScript) {
    Write-Host "错误: 找不到 industrial_watchdog.ps1 源文件" -ForegroundColor Red
    Write-Host "请确保 industrial_watchdog.ps1 与此脚本在同一目录" -ForegroundColor Yellow
    exit 1
}

# 3. 复制并更新看门狗脚本
Write-Host "复制看门狗脚本..." -ForegroundColor Yellow
$TargetScript = Join-Path $WatchdogDir "industrial_watchdog.ps1"

$ScriptContent = Get-Content $SourceScript -Raw
$ScriptContent = $ScriptContent -replace '\$BackendPath = ".*?"', "`$BackendPath = `"$BackendPath`""
$ScriptContent = $ScriptContent -replace '\$FlutterAppPath = ".*?"', "`$FlutterAppPath = `"$FlutterAppPath`""
$ScriptContent = $ScriptContent -replace '\$FlutterAppName = ".*?"', "`$FlutterAppName = `"$FlutterAppName`""

Set-Content -Path $TargetScript -Value $ScriptContent -Encoding UTF8
Write-Host "看门狗脚本已生成: $TargetScript" -ForegroundColor Green

# 4. 创建开机自启动快捷方式
Write-Host "创建开机自启动快捷方式..." -ForegroundColor Yellow

$StartupFolder = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $StartupFolder "IndustrialWatchdog.lnk"

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "powershell.exe"
$Shortcut.Arguments = "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$TargetScript`""
$Shortcut.WorkingDirectory = $WatchdogDir
$Shortcut.Description = "工控机综合看门狗（后端+Docker+Flutter）"
$Shortcut.Save()

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "看门狗安装完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "配置信息:" -ForegroundColor Cyan
Write-Host "  后端路径: $BackendPath" -ForegroundColor White
Write-Host "  Flutter App: $FlutterAppPath" -ForegroundColor White
Write-Host "  Flutter 进程名: $FlutterAppName" -ForegroundColor White
Write-Host "  看门狗脚本: $TargetScript" -ForegroundColor White
Write-Host "  自启动快捷方式: $ShortcutPath" -ForegroundColor White
Write-Host "  日志文件: $WatchdogDir\watchdog_log.txt" -ForegroundColor White
Write-Host ""

# 5. 立即启动看门狗（可选）
if (-not $InstallOnly) {
    Write-Host "是否立即启动看门狗？(Y/N)" -ForegroundColor Yellow -NoNewline
    $Response = Read-Host " "
    
    if ($Response -eq "Y" -or $Response -eq "y" -or $Response -eq "") {
        Write-Host "正在启动看门狗..." -ForegroundColor Yellow
        Start-Process powershell.exe -ArgumentList "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$TargetScript`"" -WindowStyle Hidden
        Start-Sleep -Seconds 3
        Write-Host "看门狗已后台启动！" -ForegroundColor Green
        Write-Host ""
        Write-Host "验证命令:" -ForegroundColor Cyan
        Write-Host "  Get-Content `"$WatchdogDir\watchdog_log.txt`" -Tail 20 -Wait" -ForegroundColor White
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "部署完成！系统将在下次启动时自动运行看门狗。" -ForegroundColor Green
Write-Host "查看日志: Get-Content `"$WatchdogDir\watchdog_log.txt`" -Tail 50 -Wait" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
