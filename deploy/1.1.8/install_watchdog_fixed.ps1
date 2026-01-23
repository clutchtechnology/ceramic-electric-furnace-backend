<#
.SYNOPSIS
    Industrial Watchdog Installer v4.0
.DESCRIPTION
    Install watchdog for Backend + Docker + Flutter App monitoring
.USAGE
    .\install_industrial_watchdog.ps1
#>

param(
    [string]$BackendPath = "D:\furnace-backend",
    [string]$FlutterAppPath = "D:\app\ceramic_electric_furnace.exe",
    [switch]$InstallOnly
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Industrial Watchdog Installer v4.0" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  Backend Path: $BackendPath" -ForegroundColor White
Write-Host "  Flutter App: $FlutterAppPath" -ForegroundColor White
Write-Host ""

# Get Flutter App process name
$FlutterAppName = if (Test-Path $FlutterAppPath) {
    (Get-Item $FlutterAppPath).BaseName
} else {
    "ceramic_electric_furnace"
    Write-Host "Warning: Flutter App path not found, using default name" -ForegroundColor Yellow
}

# 1. Create watchdog directory
$WatchdogDir = "D:\deploy\watchdog"
if (-not (Test-Path $WatchdogDir)) {
    Write-Host "Creating watchdog directory: $WatchdogDir" -ForegroundColor Yellow
    New-Item -Path $WatchdogDir -ItemType Directory -Force | Out-Null
}

# 2. Find source script
$SourceScript = $null
$PossiblePaths = @(
    ".\industrial_watchdog.ps1",
    "..\industrial_watchdog.ps1",
    (Join-Path $PSScriptRoot "industrial_watchdog.ps1")
)

foreach ($Path in $PossiblePaths) {
    if (Test-Path $Path) {
        $SourceScript = Resolve-Path $Path
        break
    }
}

if (-not $SourceScript) {
    Write-Host "ERROR: Cannot find industrial_watchdog.ps1" -ForegroundColor Red
    Write-Host "Please ensure industrial_watchdog.ps1 is in the same directory" -ForegroundColor Yellow
    exit 1
}

# 3. Copy and update watchdog script
Write-Host "Copying watchdog script..." -ForegroundColor Yellow
$TargetScript = Join-Path $WatchdogDir "industrial_watchdog.ps1"

$ScriptContent = Get-Content $SourceScript -Raw -Encoding UTF8
$ScriptContent = $ScriptContent -replace '\$BackendPath = ".*?"', "`$BackendPath = `"$BackendPath`""
$ScriptContent = $ScriptContent -replace '\$FlutterAppPath = ".*?"', "`$FlutterAppPath = `"$FlutterAppPath`""
$ScriptContent = $ScriptContent -replace '\$FlutterAppName = ".*?"', "`$FlutterAppName = `"$FlutterAppName`""

Set-Content -Path $TargetScript -Value $ScriptContent -Encoding UTF8
Write-Host "Watchdog script created: $TargetScript" -ForegroundColor Green

# 4. Create startup shortcut
Write-Host "Creating startup shortcut..." -ForegroundColor Yellow

$StartupFolder = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $StartupFolder "IndustrialWatchdog.lnk"

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "powershell.exe"
$Shortcut.Arguments = "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$TargetScript`""
$Shortcut.WorkingDirectory = $WatchdogDir
$Shortcut.Description = "Industrial Watchdog for Backend + Docker + Flutter"
$Shortcut.Save()

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Installation Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Configuration:" -ForegroundColor Cyan
Write-Host "  Backend Path: $BackendPath" -ForegroundColor White
Write-Host "  Flutter App: $FlutterAppPath" -ForegroundColor White
Write-Host "  Flutter Process: $FlutterAppName" -ForegroundColor White
Write-Host "  Watchdog Script: $TargetScript" -ForegroundColor White
Write-Host "  Startup Shortcut: $ShortcutPath" -ForegroundColor White
Write-Host "  Log File: $WatchdogDir\watchdog_log.txt" -ForegroundColor White
Write-Host ""

# 5. Start watchdog now (optional)
if (-not $InstallOnly) {
    Write-Host "Start watchdog now? (Y/N)" -ForegroundColor Yellow -NoNewline
    $Response = Read-Host " "
    
    if ($Response -eq "Y" -or $Response -eq "y" -or $Response -eq "") {
        Write-Host "Starting watchdog..." -ForegroundColor Yellow
        Start-Process powershell.exe -ArgumentList "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$TargetScript`"" -WindowStyle Hidden
        Start-Sleep -Seconds 3
        Write-Host "Watchdog started in background!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Verify with:" -ForegroundColor Cyan
        Write-Host "  Get-Content `"$WatchdogDir\watchdog_log.txt`" -Tail 20 -Wait" -ForegroundColor White
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Deployment Complete! Watchdog will auto-start on next boot." -ForegroundColor Green
Write-Host "View log: Get-Content `"$WatchdogDir\watchdog_log.txt`" -Tail 50 -Wait" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
