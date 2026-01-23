<#
.SYNOPSIS
    工控机综合看门狗安装脚本（后端+Docker+Flutter）
.DESCRIPTION
    在工控机上运行此脚本，自动部署综合看门狗并配置开机启动
    监控: 后端Python服务 + Docker服务 + Flutter App
.USAGE
    以管理员模式运行 PowerShell，执行:
    powershell -ExecutionPolicy Bypass -File install_watchdog.ps1
    
    或指定自定义路径:
    .\install_watchdog.ps1 -BackendPath "D:\furnace-backend" -FlutterAppPath "D:\app\ceramic_electric_furnace.exe"
#>

param(
    [string]$BackendPath = "D:\furnace-backend",
    [string]$FlutterAppPath = "D:\app\ceramic_electric_furnace.exe",
    [switch]$InstallOnly
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " 工控机综合看门狗 v4.0 安装程序" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "后端路径: $BackendPath" -ForegroundColor White
Write-Host "Flutter App: $FlutterAppPath" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan

# ======================== 创建看门狗目录 ========================
$WatchdogDir = "D:\deploy\watchdog"
if (-not (Test-Path $WatchdogDir)) {
    Write-Host "创建看门狗目录: $WatchdogDir" -ForegroundColor Yellow
    New-Item -Path $WatchdogDir -ItemType Directory -Force | Out-Null
}

# ======================== 生成看门狗脚本内容 ========================
$WatchdogScriptContent = @"
<#
.SYNOPSIS
    工控机综合看门狗 v4.0 (Backend + Docker + Flutter App)
#>

# ======================== 配置区 ========================
`$BackendPath = "$BackendPath"
`$BackendScript = "main.py"
`$BackendPython = "venv\Scripts\python.exe"
`$BackendProcessName = "python"

`$FlutterAppPath = "$FlutterAppPath"
`$FlutterAppName = "$((Get-Item $FlutterAppPath -ErrorAction SilentlyContinue).BaseName)"

`$CheckInterval = 10
`$MaxFreezeCount = 6
`$LogFile = "D:\deploy\watchdog\watchdog_log.txt"
`$MaxLogSize = 10MB
# ========================================================

$CurrentFreezeCount = 0
$script:CurrentDockerComposePath = $null

function Test-SingleInstance {
    if (Test-Path $LockFile) {
        $lockPid = Get-Content $LockFile -ErrorAction SilentlyContinue
        if ($lockPid -and (Get-Process -Id $lockPid -ErrorAction SilentlyContinue)) {
            Write-Host "看门狗已在运行 (PID: $lockPid)，退出..." -ForegroundColor Yellow
            exit 0
        }
    }
    $PID | Out-File -FilePath $LockFile -Force
}

function Remove-Lock { Remove-Item -Path $LockFile -Force -ErrorAction SilentlyContinue }

function Write-Log {
    param ($Message, $Level = "INFO")
    $TimeStamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $Color = switch ($Level) { "ERROR" { "Red" } "WARN" { "Yellow" } "OK" { "Green" } default { "Cyan" } }
    $LogEntry = "[$TimeStamp] [$Level] $Message"
    Write-Host $LogEntry -ForegroundColor $Color
    Add-Content -Path $LogFile -Value $LogEntry -ErrorAction SilentlyContinue
}

function Get-LatestDeployPath {
    $deployDirs = Get-ChildItem -Path $DeployRootPath -Directory -ErrorAction SilentlyContinue | 
        Where-Object { Test-Path (Join-Path $_.FullName "docker-compose.yml") } |
        Sort-Object { 
            $version = $_.Name -replace '[^\d.]', ''
            if ($version -match '^[\d.]+$') {
                $parts = $version.Split('.') | ForEach-Object { [int]$_ }
                while ($parts.Count -lt 4) { $parts += 0 }
                $parts[0] * 1000000 + $parts[1] * 10000 + $parts[2] * 100 + $parts[3]
            } else {
                (Get-Item $_.FullName).LastWriteTime.Ticks
            }
        } -Descending
    if ($deployDirs) { return $deployDirs[0].FullName }
    return $null
}

function Test-DockerRunning {
    try {
        $null = docker info 2>&1
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Ensure-DockerRunning {
    $dockerProcess = Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue
    if (-not $dockerProcess) {
        Write-Log "Docker Desktop 未运行，正在启动..." "WARN"
        Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
        Write-Log "等待 Docker 启动 (60秒)..."
        Start-Sleep -Seconds 60
    }
    for ($i = 0; $i -lt 12; $i++) {
        if (Test-DockerRunning) {
            Write-Log "Docker 已就绪" "OK"
            return $true
        }
        Write-Log "等待 Docker daemon... ($i/12)"
        Start-Sleep -Seconds 5
    }
    Write-Log "Docker 启动失败" "ERROR"
    return $false
}

function Ensure-BackendRunning {
    $latestPath = Get-LatestDeployPath
    if (-not $latestPath) { Write-Log "未找到 deploy 目录" "ERROR"; return }
    
    if ($latestPath -ne $script:CurrentDockerComposePath) {
        Write-Log "检测到部署目录: $latestPath" "OK"
        $script:CurrentDockerComposePath = $latestPath
    }
    
    $allRunning = $true
    foreach ($container in $BackendContainers) {
        $status = docker ps --filter "name=$container" --format "{{.Status}}" 2>$null
        if (-not $status -or $status -notlike "Up*") {
            $allRunning = $false
            Write-Log "容器 $container 未运行" "WARN"
        }
    }
    if (-not $allRunning) {
        Write-Log "正在从 $script:CurrentDockerComposePath 启动后端服务..."
        Push-Location $script:CurrentDockerComposePath
        docker compose up -d 2>&1 | Out-Null
        Pop-Location
        Start-Sleep -Seconds 15
        foreach ($container in $BackendContainers) {
            $status = docker ps --filter "name=$container" --format "{{.Status}}" 2>$null
            if ($status -like "Up*") {
                Write-Log "容器 $container 已启动" "OK"
            } else {
                Write-Log "容器 $container 启动失败" "ERROR"
            }
        }
    }
}

function Force-Kill-App {
    Write-Log "正在强制关闭 App..."
    Get-Process -Name $AppName -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
    taskkill /F /T /IM "${AppName}.exe" 2>$null
    $Retry = 0
    while ((Get-Process -Name $AppName -ErrorAction SilentlyContinue) -and ($Retry -lt 5)) {
        Start-Sleep -Seconds 1
        taskkill /F /T /IM "${AppName}.exe" 2>$null
        $Retry++
    }
    if (-not (Get-Process -Name $AppName -ErrorAction SilentlyContinue)) {
        Write-Log "App 已关闭" "OK"
        return $true
    }
    Write-Log "无法关闭 App" "ERROR"
    return $false
}

function Start-App {
    Write-Log "正在启动 Flutter App..."
    try {
        Start-Process -FilePath $AppPath -WorkingDirectory (Split-Path $AppPath)
        Start-Sleep -Seconds 5
        if (Get-Process -Name $AppName -ErrorAction SilentlyContinue) {
            Write-Log "Flutter App 已启动" "OK"
        }
    } catch {
        Write-Log "启动失败: $_" "ERROR"
    }
}

function Check-AppResponding {
    $Processes = Get-Process -Name $AppName -ErrorAction SilentlyContinue
    if (-not $Processes) { return $null }
    foreach ($p in $Processes) {
        try { $p.Refresh() } catch {}
        if (-not $p.Responding) { return $false }
    }
    return $true
}

# ======================== 主程序 ========================
try {
    Test-SingleInstance
    Write-Log "========================================"
    Write-Log "电炉系统看门狗 v3.2 启动 (自动版本检测)" "OK"
    Write-Log "部署目录: $DeployRootPath"
    Write-Log "========================================"
    
    $initialPath = Get-LatestDeployPath
    if ($initialPath) {
        Write-Log "检测到最新部署: $initialPath" "OK"
        $script:CurrentDockerComposePath = $initialPath
    } else {
        Write-Log "警告: 未找到任何部署目录" "WARN"
    }
    
    if (Ensure-DockerRunning) { Ensure-BackendRunning }
    if (-not (Get-Process -Name $AppName -ErrorAction SilentlyContinue)) { Start-App }
    
    while ($true) {
        # 检查 Docker
        if (-not (Test-DockerRunning)) {
            Write-Log "Docker 异常" "ERROR"
            Ensure-DockerRunning
        }
        
        # 检查后端
        Ensure-BackendRunning
        
        # 检查 App
        $appStatus = Check-AppResponding
        if ($appStatus -eq $null) {
            Write-Log "App 未运行，正在启动..." "WARN"
            $CurrentFreezeCount = 0
            Start-App
            Start-Sleep -Seconds 10
        } elseif ($appStatus -eq $false) {
            $CurrentFreezeCount++
            Write-Log "App 未响应 - 计数 $CurrentFreezeCount / $MaxFreezeCount" "WARN"
            if ($CurrentFreezeCount -ge $MaxFreezeCount) {
                Write-Log "App 卡死，强制重启!" "ERROR"
                if (Force-Kill-App) {
                    Start-Sleep -Seconds 3
                    Start-App
                    Start-Sleep -Seconds 15
                }
                $CurrentFreezeCount = 0
            }
        } else {
            if ($CurrentFreezeCount -gt 0) {
                Write-Log "App 恢复响应" "OK"
                $CurrentFreezeCount = 0
            }
        }
        
        Start-Sleep -Seconds $CheckInterval
    }
} finally {
    Remove-Lock
    Write-Log "看门狗已退出" "WARN"
}
'@ | Out-File -FilePath "D:\furnace_watchdog.ps1" -Encoding UTF8 -Force

Write-Host "`n[1/3] 看门狗脚本已创建: D:\furnace_watchdog.ps1" -ForegroundColor Green

# ======================== 创建开机启动快捷方式 ========================
$WshShell = New-Object -ComObject WScript.Shell
$StartupPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
$ShortcutPath = "$StartupPath\FurnaceWatchdog.lnk"
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "powershell.exe"
$Shortcut.Arguments = "-ExecutionPolicy Bypass -WindowStyle Hidden -File D:\furnace_watchdog.ps1"
$Shortcut.WorkingDirectory = "D:\"
$Shortcut.Description = "电炉系统看门狗"
$Shortcut.Save()

Write-Host "[2/3] 开机启动已配置: $ShortcutPath" -ForegroundColor Green

# ======================== 显示检测到的目录 ========================
Write-Host "[3/3] 扫描部署目录..." -ForegroundColor Green

$detected = Get-ChildItem -Path "D:\deploy" -Directory -ErrorAction SilentlyContinue | 
Where-Object { Test-Path (Join-Path $_.FullName "docker-compose.yml") } |
Sort-Object Name -Descending | Select-Object -First 5

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " 安装完成!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host " 脚本位置:   D:\furnace_watchdog.ps1" -ForegroundColor Cyan
Write-Host " 日志位置:   D:\watchdog_log.txt" -ForegroundColor Cyan
Write-Host " 开机启动:   已配置" -ForegroundColor Cyan
Write-Host ""

if ($detected) {
  Write-Host " 检测到的部署目录:" -ForegroundColor Yellow
  foreach ($d in $detected) { 
    Write-Host "   - $($d.Name)" -ForegroundColor White 
  }
  Write-Host ""
}

Write-Host " 手动启动命令:" -ForegroundColor Yellow
Write-Host " powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File D:\furnace_watchdog.ps1" -ForegroundColor White
Write-Host ""

# ======================== 询问是否立即启动 ========================
Write-Host "立即启动看门狗? (Y/N): " -NoNewline -ForegroundColor Yellow
$confirm = Read-Host
if ($confirm -match "^[Yy]") { 
  # 先停止可能正在运行的看门狗
  if (Test-Path "D:\watchdog.lock") {
    $oldPid = Get-Content "D:\watchdog.lock" -ErrorAction SilentlyContinue
    if ($oldPid) {
      Stop-Process -Id $oldPid -Force -ErrorAction SilentlyContinue
      Start-Sleep -Seconds 1
    }
  }
  # 以隐藏窗口模式启动
  Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -WindowStyle Hidden -File D:\furnace_watchdog.ps1" -WindowStyle Hidden
  Write-Host ""
  Write-Host "看门狗已在后台启动! (无窗口)" -ForegroundColor Green
}
else {
  Write-Host ""
  Write-Host "已跳过，可稍后手动启动" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "按任意键退出..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
