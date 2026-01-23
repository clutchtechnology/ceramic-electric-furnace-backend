<#
.SYNOPSIS
    工控机综合看门狗 (Backend + Docker + Flutter App 监控)
.DESCRIPTION
    1. 监控后端Python服务是否运行（后台运行）
    2. 监控Docker服务是否启动
    3. 监控Flutter App是否崩溃/卡死
    4. 开机自启动，全自动恢复
.NOTES
    部署方式: 
    1. 将此脚本放到 D:\deploy\watchdog\ 目录
    2. 创建快捷方式到启动文件夹: shell:startup
    3. 快捷方式目标: powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -File "D:\deploy\watchdog\industrial_watchdog.ps1"
#>

# ======================== 配置区 ========================
$BackendPath = "D:\furnace-backend"
$BackendScript = "main.py"
$BackendPython = "venv\Scripts\python.exe"
$BackendProcessName = "python"  # 用于识别后端进程的关键字

$FlutterAppPath = "D:\app\ceramic_electric_furnace.exe"
$FlutterAppName = "ceramic_electric_furnace"

$CheckInterval = 10  # 检查间隔（秒）
$MaxFreezeCount = 6  # Flutter App 连续无响应次数阈值（60秒）
$LogFile = "D:\deploy\watchdog\watchdog_log.txt"
$MaxLogSize = 10MB   # 日志文件最大10MB，超过自动清理

# ======================== 日志函数 ========================
function Write-Log {
    param ($Message, $Level = "INFO")
    $TimeStamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogEntry = "[$TimeStamp][$Level] $Message"
    
    $Color = switch ($Level) {
        "ERROR" { "Red" }
        "WARN"  { "Yellow" }
        "OK"    { "Green" }
        default { "Cyan" }
    }
    Write-Host $LogEntry -ForegroundColor $Color
    
    try {
        Add-Content -Path $LogFile -Value $LogEntry -ErrorAction SilentlyContinue
        
        # 日志文件大小控制
        if (Test-Path $LogFile) {
            $LogSize = (Get-Item $LogFile).Length
            if ($LogSize -gt $MaxLogSize) {
                Write-Host "日志文件超过 $($MaxLogSize/1MB)MB，正在清理旧日志..." -ForegroundColor Yellow
                $Content = Get-Content $LogFile -Tail 1000
                Set-Content $LogFile -Value $Content
            }
        }
    } catch {
        Write-Host "日志写入失败: $_" -ForegroundColor Red
    }
}

# ======================== Docker 监控 ========================
function Check-DockerService {
    try {
        $DockerService = Get-Service -Name "Docker" -ErrorAction SilentlyContinue
        
        if (-not $DockerService) {
            Write-Log "Docker 服务未安装，跳过检查" "WARN"
            return $true
        }
        
        if ($DockerService.Status -ne "Running") {
            Write-Log "Docker 服务未运行，正在启动..." "WARN"
            Start-Service -Name "Docker"
            Start-Sleep -Seconds 10
            
            $DockerService.Refresh()
            if ($DockerService.Status -eq "Running") {
                Write-Log "Docker 服务启动成功" "OK"
                return $true
            } else {
                Write-Log "Docker 服务启动失败" "ERROR"
                return $false
            }
        }
        return $true
    } catch {
        Write-Log "Docker 检查异常: $_" "ERROR"
        return $false
    }
}

# ======================== 后端服务监控 ========================
function Get-BackendProcess {
    # 通过命令行参数识别后端进程（避免误杀其他Python进程）
    $AllPythonProcesses = Get-WmiObject Win32_Process -Filter "name='python.exe'" -ErrorAction SilentlyContinue
    
    foreach ($proc in $AllPythonProcesses) {
        if ($proc.CommandLine -like "*$BackendScript*") {
            return Get-Process -Id $proc.ProcessId -ErrorAction SilentlyContinue
        }
    }
    return $null
}

function Start-BackendService {
    Write-Log "正在启动后端服务..."
    
    if (-not (Test-Path (Join-Path $BackendPath $BackendPython))) {
        Write-Log "后端Python环境不存在: $BackendPath\$BackendPython" "ERROR"
        return $false
    }
    
    try {
        $PythonExe = Join-Path $BackendPath $BackendPython
        
        # 使用 cmd /c start 启动后台进程（最可靠的方法）
        $Command = "cmd /c start /B `"Backend`" `"$PythonExe`" $BackendScript"
        
        # 在后端目录执行启动命令
        Push-Location $BackendPath
        Invoke-Expression $Command
        Pop-Location
        
        # 等待进程启动并稳定
        Start-Sleep -Seconds 10
        
        # 验证进程是否还在运行
        $BackendProc = Get-BackendProcess
        if ($BackendProc) {
            Write-Log "后端服务启动成功 (PID: $($BackendProc.Id))" "OK"
            return $true
        } else {
            Write-Log "后端服务启动失败（进程未检测到）" "ERROR"
            Write-Log "尝试手动启动: cd $BackendPath; .\$BackendPython $BackendScript" "ERROR"
            return $false
        }
    } catch {
        Write-Log "后端服务启动异常: $_" "ERROR"
        return $false
    }
}

function Check-BackendService {
    $BackendProc = Get-BackendProcess
    
    if (-not $BackendProc) {
        Write-Log "后端服务未运行" "WARN"
        return Start-BackendService
    }
    
    # 检查进程是否僵死（可选：通过HTTP健康检查）
    try {
        $HealthCheck = Invoke-WebRequest -Uri "http://localhost:8082/api/health" -TimeoutSec 5 -UseBasicParsing -ErrorAction SilentlyContinue
        if ($HealthCheck.StatusCode -eq 200) {
            return $true
        } else {
            Write-Log "后端服务健康检查失败 (HTTP $($HealthCheck.StatusCode))" "WARN"
            Write-Log "正在重启后端服务..."
            Stop-Process -Id $BackendProc.Id -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 3
            return Start-BackendService
        }
    } catch {
        Write-Log "后端服务健康检查超时" "WARN"
        return $true  # 可能网络问题，不强制重启
    }
}

# ======================== Flutter App 监控 ========================
$FlutterFreezeCount = 0

function Force-Kill-FlutterApp {
    Write-Log "正在强制关闭 Flutter App..."
    
    Get-Process -Name $FlutterAppName -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
    taskkill /F /T /IM "${FlutterAppName}.exe" 2>$null
    
    $Retry = 0
    while ((Get-Process -Name $FlutterAppName -ErrorAction SilentlyContinue) -and ($Retry -lt 5)) {
        Write-Log "等待 Flutter App 进程释放... ($Retry)"
        Start-Sleep -Seconds 1
        taskkill /F /T /IM "${FlutterAppName}.exe" 2>$null
        $Retry++
    }
    
    if (Get-Process -Name $FlutterAppName -ErrorAction SilentlyContinue) {
        Write-Log "无法杀死 Flutter App 进程" "ERROR"
        return $false
    }
    
    Write-Log "Flutter App 已成功关闭" "OK"
    return $true
}

function Start-FlutterApp {
    Write-Log "正在启动 Flutter App..."
    
    if (-not (Test-Path $FlutterAppPath)) {
        Write-Log "Flutter App 路径不存在: $FlutterAppPath" "ERROR"
        return $false
    }
    
    try {
        Start-Process -FilePath $FlutterAppPath -WorkingDirectory (Split-Path $FlutterAppPath)
        Write-Log "Flutter App 启动成功" "OK"
        return $true
    } catch {
        Write-Log "Flutter App 启动失败: $_" "ERROR"
        return $false
    }
}

function Check-FlutterApp {
    $Processes = Get-Process -Name $FlutterAppName -ErrorAction SilentlyContinue
    
    if (-not $Processes) {
        # 进程不存在（崩溃）
        if ($script:FlutterFreezeCount -gt 0) { $script:FlutterFreezeCount = 0 }
        Write-Log "Flutter App 已退出，正在重启..." "WARN"
        Force-Kill-FlutterApp
        Start-FlutterApp
        Start-Sleep -Seconds 10
        return
    }
    
    # 检查是否卡死
    $AllResponding = $true
    foreach ($p in $Processes) {
        try { $p.Refresh() } catch {}
        if (-not $p.Responding) {
            $AllResponding = $false
            break
        }
    }
    
    if (-not $AllResponding) {
        $script:FlutterFreezeCount++
        Write-Log "Flutter App 未响应 (计数: $script:FlutterFreezeCount / $MaxFreezeCount)" "WARN"
        
        if ($script:FlutterFreezeCount -ge $MaxFreezeCount) {
            Write-Log "Flutter App 永久卡死，正在重启..." "ERROR"
            if (Force-Kill-FlutterApp) {
                Start-Sleep -Seconds 2
                Start-FlutterApp
                Start-Sleep -Seconds 15
            }
            $script:FlutterFreezeCount = 0
        }
    } else {
        if ($script:FlutterFreezeCount -gt 0) {
            Write-Log "Flutter App 恢复响应" "OK"
            $script:FlutterFreezeCount = 0
        }
    }
}

# ======================== 主监控循环 ========================
Write-Log "========================================" "OK"
Write-Log "工控机综合看门狗启动 (v1.0)" "OK"
Write-Log "后端路径: $BackendPath" "INFO"
Write-Log "Flutter App: $FlutterAppPath" "INFO"
Write-Log "检查间隔: ${CheckInterval}秒" "INFO"
Write-Log "========================================" "OK"

# 初始化启动
Write-Log "初始化检查..."
Check-DockerService
if (-not (Get-BackendProcess)) {
    Start-BackendService
}
if (-not (Get-Process -Name $FlutterAppName -ErrorAction SilentlyContinue)) {
    Start-FlutterApp
}

$IterationCount = 0

while ($true) {
    $IterationCount++
    
    # 每10次迭代输出一次心跳日志
    if ($IterationCount % 10 -eq 0) {
        Write-Log "心跳检查 (已运行 $($IterationCount * $CheckInterval) 秒)" "INFO"
    }
    
    # 1. 检查 Docker（每分钟检查一次）
    if ($IterationCount % 6 -eq 0) {
        Check-DockerService | Out-Null
    }
    
    # 2. 检查后端服务
    Check-BackendService | Out-Null
    
    # 3. 检查 Flutter App
    Check-FlutterApp
    
    Start-Sleep -Seconds $CheckInterval
}
