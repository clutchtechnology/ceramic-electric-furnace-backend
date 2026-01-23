# 工控机看门狗部署指南

## 功能说明

综合看门狗系统监控以下服务：

1. **后端 Python 服务**（FastAPI）
   - 自动启动并保持后台运行
   - 每10秒检查进程是否存活
   - 通过 HTTP 健康检查验证服务状态
   - 异常时自动重启

2. **Docker 服务**
   - 每60秒检查一次 Docker 服务状态
   - 自动启动未运行的 Docker 服务
   - 确保 InfluxDB 容器正常运行

3. **Flutter App**
   - 监控进程是否存活（崩溃检测）
   - 监控 UI 是否响应（卡死检测）
   - 连续60秒未响应自动重启
   - 强制清理僵尸进程

## 部署步骤（工控机）

### 方法一：一键安装（推荐）

在工控机 PowerShell 中运行：

```powershell
# 1. 进入部署目录（假设你已将文件放到工控机）
cd D:\deploy\1.1.8

# 2. 运行安装脚本（默认路径）
.\install_watchdog.ps1

# 或指定自定义路径
.\install_watchdog.ps1 -BackendPath "D:\furnace-backend" -FlutterAppPath "D:\app\ceramic_electric_furnace.exe"
```

安装脚本会：
- 创建 `D:\deploy\watchdog\` 目录
- 复制看门狗脚本到该目录
- 创建开机自启动快捷方式
- 询问是否立即启动

### 方法二：手动部署

```powershell
# 1. 创建看门狗目录
New-Item -Path "D:\deploy\watchdog" -ItemType Directory -Force

# 2. 复制看门狗脚本
Copy-Item ".\industrial_watchdog.ps1" -Destination "D:\deploy\watchdog\" -Force

# 3. 编辑脚本，修改以下路径（如果需要）
notepad D:\deploy\watchdog\industrial_watchdog.ps1
```

在脚本顶部修改：
```powershell
$BackendPath = "D:\furnace-backend"  # 后端实际路径
$FlutterAppPath = "D:\app\ceramic_electric_furnace.exe"  # Flutter App 实际路径
```

```powershell
# 4. 创建开机自启动（手动）
# 方式1: 快捷方式到启动文件夹
$StartupFolder = [Environment]::GetFolderPath("Startup")
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$StartupFolder\IndustrialWatchdog.lnk")
$Shortcut.TargetPath = "powershell.exe"
$Shortcut.Arguments = '-WindowStyle Hidden -ExecutionPolicy Bypass -File "D:\deploy\watchdog\industrial_watchdog.ps1"'
$Shortcut.Save()

# 方式2: 任务计划程序（更可靠）
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument '-WindowStyle Hidden -ExecutionPolicy Bypass -File "D:\deploy\watchdog\industrial_watchdog.ps1"'
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -LogonType Interactive -RunLevel Highest
Register-ScheduledTask -TaskName "IndustrialWatchdog" -Action $Action -Trigger $Trigger -Principal $Principal -Force

# 5. 立即启动看门狗（后台运行）
Start-Process powershell.exe -ArgumentList '-WindowStyle Hidden -ExecutionPolicy Bypass -File "D:\deploy\watchdog\industrial_watchdog.ps1"' -WindowStyle Hidden
```

## 验证部署

```powershell
# 1. 检查看门狗进程是否运行
Get-Process powershell | Where-Object { $_.CommandLine -like "*industrial_watchdog*" }

# 2. 实时查看日志
Get-Content "D:\deploy\watchdog\watchdog_log.txt" -Tail 50 -Wait

# 3. 检查各服务状态
# 后端服务
Invoke-WebRequest -Uri "http://localhost:8082/api/health" -UseBasicParsing

# Docker 服务
Get-Service Docker

# Flutter App
Get-Process ceramic_electric_furnace
```

## 日常运维

### 查看日志

```powershell
# 实时监控
Get-Content "D:\deploy\watchdog\watchdog_log.txt" -Tail 100 -Wait

# 查看最近错误
Get-Content "D:\deploy\watchdog\watchdog_log.txt" | Select-String "ERROR"

# 查看最近警告
Get-Content "D:\deploy\watchdog\watchdog_log.txt" | Select-String "WARN"
```

### 手动控制服务

```powershell
# 停止看门狗
Get-Process powershell | Where-Object { $_.CommandLine -like "*industrial_watchdog*" } | Stop-Process -Force

# 启动看门狗
Start-Process powershell.exe -ArgumentList '-WindowStyle Hidden -ExecutionPolicy Bypass -File "D:\deploy\watchdog\industrial_watchdog.ps1"' -WindowStyle Hidden

# 重启看门狗
Get-Process powershell | Where-Object { $_.CommandLine -like "*industrial_watchdog*" } | Stop-Process -Force
Start-Sleep -Seconds 2
Start-Process powershell.exe -ArgumentList '-WindowStyle Hidden -ExecutionPolicy Bypass -File "D:\deploy\watchdog\industrial_watchdog.ps1"' -WindowStyle Hidden
```

### 卸载看门狗

```powershell
# 1. 停止看门狗
Get-Process powershell | Where-Object { $_.CommandLine -like "*industrial_watchdog*" } | Stop-Process -Force

# 2. 删除开机自启动
Remove-Item "$([Environment]::GetFolderPath('Startup'))\IndustrialWatchdog.lnk" -Force -ErrorAction SilentlyContinue

# 或删除任务计划
Unregister-ScheduledTask -TaskName "IndustrialWatchdog" -Confirm:$false -ErrorAction SilentlyContinue

# 3. 删除看门狗文件（可选）
Remove-Item "D:\deploy\watchdog" -Recurse -Force -ErrorAction SilentlyContinue
```

## 故障排查

### 问题1: 后端服务无法启动

```powershell
# 检查后端路径是否正确
Test-Path "D:\furnace-backend\venv\Scripts\python.exe"
Test-Path "D:\furnace-backend\main.py"

# 手动测试启动
cd D:\furnace-backend
.\venv\Scripts\python.exe main.py

# 检查端口占用
netstat -ano | findstr "8082"
```

### 问题2: Flutter App 频繁重启

查看日志中的 `Flutter App 未响应` 记录，可能原因：
- 内存不足（检查任务管理器）
- PLC 连接问题（检查后端健康接口）
- 数据刷新过快（调整 `$CheckInterval` 和 `$MaxFreezeCount`）

```powershell
# 增加容忍度（修改脚本）
$CheckInterval = 15         # 改为15秒检查一次
$MaxFreezeCount = 10        # 改为150秒无响应才重启
```

### 问题3: Docker 服务检查失败

```powershell
# 手动检查 Docker 服务
Get-Service Docker

# 手动启动 Docker
Start-Service Docker

# 检查 Docker 容器
docker ps -a

# 启动 InfluxDB 容器
docker compose -f D:\furnace-backend\docker-compose.yml up -d
```

### 问题4: 看门狗自身崩溃

查看 Windows 事件查看器：
```powershell
Get-EventLog -LogName Application -Source "Windows PowerShell" -Newest 20
```

如果持续崩溃，可启用详细日志：
```powershell
# 在 industrial_watchdog.ps1 开头添加
$VerbosePreference = "Continue"
Start-Transcript -Path "D:\deploy\watchdog\transcript_log.txt" -Append
```

## 性能调优

### 低性能工控机（4GB 内存）

```powershell
# 减少检查频率
$CheckInterval = 20         # 改为20秒
$MaxFreezeCount = 3         # 60秒无响应重启

# 禁用后端健康检查（减少网络开销）
# 注释掉 Check-BackendService 中的 Invoke-WebRequest 部分
```

### 高性能工控机（8GB+ 内存）

```powershell
# 增加检查频率
$CheckInterval = 5          # 5秒检查
$MaxFreezeCount = 12        # 60秒无响应重启

# 启用更详细的健康检查
```

## 配置文件说明

| 配置项                | 默认值                                     | 说明                     |
| --------------------- | ------------------------------------------ | ------------------------ |
| `$BackendPath`        | `D:\furnace-backend`                       | 后端项目根目录           |
| `$BackendScript`      | `main.py`                                  | 后端启动脚本             |
| `$BackendPython`      | `venv\Scripts\python.exe`                  | Python 虚拟环境路径      |
| `$FlutterAppPath`     | `D:\app\ceramic_electric_furnace.exe`      | Flutter App 完整路径     |
| `$FlutterAppName`     | `ceramic_electric_furnace`                 | 进程名（不含 .exe）      |
| `$CheckInterval`      | `10`                                       | 检查间隔（秒）           |
| `$MaxFreezeCount`     | `6`                                        | 无响应次数阈值（60秒）   |
| `$LogFile`            | `D:\deploy\watchdog\watchdog_log.txt`      | 日志文件路径             |
| `$MaxLogSize`         | `10MB`                                     | 日志文件最大大小         |

## 注意事项

1. **权限要求**: 看门狗需要管理员权限（用于重启服务）
2. **网络依赖**: 后端健康检查需要 localhost 网络可达
3. **日志管理**: 自动清理超过 10MB 的日志文件
4. **进程识别**: 通过命令行参数识别后端进程（避免误杀）
5. **多实例**: 如果有多个 Python 进程，确保 `$BackendScript` 名称唯一

## 高级配置

### 自定义健康检查逻辑

编辑 `Check-BackendService` 函数：

```powershell
# 例如：增加数据库连接检查
try {
    $HealthCheck = Invoke-WebRequest -Uri "http://localhost:8082/api/health" -TimeoutSec 5 -UseBasicParsing
    $HealthData = $HealthCheck.Content | ConvertFrom-Json
    
    if ($HealthData.influxdb_connected -eq $false) {
        Write-Log "InfluxDB 连接失败" "ERROR"
        # 重启 Docker 容器
        docker compose -f D:\furnace-backend\docker-compose.yml restart influxdb
    }
} catch {
    # 错误处理
}
```

### 添加邮件/微信告警

在关键错误处添加告警：

```powershell
function Send-Alert {
    param ($Message)
    # 调用企业微信 Webhook 或邮件 API
    Invoke-WebRequest -Uri "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY" `
        -Method Post -Body (@{msgtype="text"; text=@{content=$Message}} | ConvertTo-Json) `
        -ContentType "application/json"
}

# 在需要告警的地方调用
Send-Alert "工控机后端服务多次启动失败！"
```

## 联系与支持

- 日志路径: `D:\deploy\watchdog\watchdog_log.txt`
- 配置文件: `D:\deploy\watchdog\industrial_watchdog.ps1`
- 开机自启动: `shell:startup\IndustrialWatchdog.lnk`
