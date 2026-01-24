# Ceramic Electric Furnace Backend - AI Coding Guidelines

> **Project Identity**: `ceramic-electric-furnace-backend` (FastAPI + InfluxDB + S7-1200)
> **Role**: AI Assistant for Industrial IoT Backend Development
> **Language**: 中文回答

---

## 1. 核心架构原则

| 原则 | 说明 |
|------|------|
| **数据与状态分离** | Data (DB32) → InfluxDB 存储；Status (DB30) → 内存缓存 |
| **模块化配置** | 基础模块定义在 `configs/plc_modules.yaml`，通过 `module_ref` 引用 |
| **PLC 模式** | 工控机部署，不考虑 Mock 模式，使用 `python-snap7` 长连接 |

---

## 2. 数据流架构

```
S7-1200 PLC
    ↓ (DB32/DB30)
PollingService (PLC Manager + Parser)
    ↓
├─ Data Buffer → InfluxDB (批量写入)
└─ Memory Cache → FastAPI API
```

---

## 3. 项目结构

```
ceramic-electric-furnace-backend/
├── main.py                    # FastAPI 入口
├── config.py                  # 全局配置
├── configs/                   # [核心配置]
│   ├── plc_modules.yaml       # 基础模块定义
│   ├── config_L3_P2_F2_C4.yaml   # DB32 配置
│   ├── status_L3_P2_F2_C4.yaml   # DB30 配置
│   └── db_mappings.yaml       # DB 块映射
├── app/
│   ├── plc/                   # PLC 通信层
│   │   ├── plc_manager.py     # 单例连接管理器
│   │   ├── parser_modbus.py   # DB32 解析器
│   │   └── parser_status.py   # DB30 解析器
│   ├── services/              # 业务逻辑层
│   │   ├── polling_service.py # 轮询核心
│   │   └── furnace_service.py # 业务查询
│   ├── tools/                 # 转换工具
│   │   └── converter_*.py     # 原始值 → 物理量
│   └── routers/               # API 路由
│       ├── furnace.py         # 业务接口
│       └── monitor.py         # 监控接口
└── docker-compose.yml         # 容器编排
```

---

## 4. 实现规范

### 4.1 配置引用

**基础定义** (`configs/plc_modules.yaml`):
```yaml
modules:
  InfraredDistance:
    size: 4
    fields: [{name: HIGH, type: WORD}, {name: LOW, type: WORD}]
```

**实例化** (`configs/config_*.yaml`):
```yaml
modules:
  - name: LENTH_1
    module_ref: InfraredDistance
    offset: 0
```

### 4.2 轮询服务 (`polling_service.py`)

1. **单例管理**: 从 `app.plc.plc_manager` 获取 `get_plc_manager()`
2. **异常隔离**: 解析错误不中断轮询循环
3. **特殊处理**: DB32 偏移量 28 (MBrly) 是写寄存器，解析时跳过
4. **批量写入**: InfluxDB 使用 `write_points_batch`

### 4.3 PLC 字节序

- **S7-1200**: Big Endian
- **Python**: `struct.unpack('>H', ...)` (WORD), `'>f'` (REAL)

---

## 5. API 接口

| 端点 | 说明 |
|------|------|
| `GET /api/monitor/realtime` | DB32 解析后的物理量 |
| `GET /api/monitor/status` | DB30 解析后的通信状态 |
| `GET /api/furnace/history` | InfluxDB 历史趋势 |

**Base URL**: `http://localhost:8082`

**端口映射**: InfluxDB → 8088

---

## 6. 工控机部署

### 6.1 部署目录

```
D:\deploy\1.1.8\          # 部署包目录
D:\furnace-backend\       # 运行目录
D:\electric\Release\      # Flutter 应用目录
```

### 6.2 部署命令

```powershell
# 停止旧服务 → 解压新包 → 启动服务
cd D:\deploy\1.1.8; Expand-Archive -Path "furnace-backend-1.1.8.zip" -DestinationPath "D:\furnace-backend" -Force; cd D:\furnace-backend; .\venv\Scripts\python.exe main.py
```

### 6.3 看门狗脚本

```powershell
# 创建看门狗
$WatchdogPath = "D:\deploy\watchdog_simple.ps1"
$WatchdogContent = @'
while ($true) {
    # 后端检查
    $Backend = Get-WmiObject Win32_Process -Filter "name='python.exe'" | Where-Object { $_.CommandLine -like "*main.py*" }
    if (-not $Backend) {
        Start-Process powershell.exe -ArgumentList '-NoExit', '-Command', 'cd D:\furnace-backend; .\venv\Scripts\python.exe main.py' -WindowStyle Hidden
        Start-Sleep -Seconds 15
    }
    
    # Flutter 检查
    $Flutter = Get-Process -Name "ceramic_electric_furnace_flutter" -ErrorAction SilentlyContinue
    if (-not $Flutter) {
        Start-Process "D:\electric\Release\ceramic_electric_furnace_flutter.exe"
        Start-Sleep -Seconds 10
    } elseif (-not $Flutter.Responding) {
        Stop-Process -Id $Flutter.Id -Force
        Start-Sleep -Seconds 3
        Start-Process "D:\electric\Release\ceramic_electric_furnace_flutter.exe"
        Start-Sleep -Seconds 10
    }
    
    Start-Sleep -Seconds 10
}
'@

New-Item -Path (Split-Path $WatchdogPath) -ItemType Directory -Force | Out-Null
Set-Content -Path $WatchdogPath -Value $WatchdogContent -Encoding UTF8

# 创建开机自启动任务
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$WatchdogPath`""
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -LogonType Interactive -RunLevel Highest
Register-ScheduledTask -TaskName "IndustrialWatchdog" -Action $Action -Trigger $Trigger -Principal $Principal -Description "Backend + Flutter Watchdog" -Force

# 启动看门狗
Start-ScheduledTask -TaskName "IndustrialWatchdog"
```

---

## 7. AI 指令

1. 生成代码时，优先参考 `configs/` 目录定义，不要硬编码偏移量
2. 工控机部署，不考虑 Mock 模式
3. 测试脚本提供可直接在工控机运行的命令行，不创建本地脚本文件
然后部署的话,可能需要先解压,然后再启动服务就行了
4. 接下来我打算就是,1,为我的前后端的全部的整理,并且梳理api内部的实现逻辑,并且考虑我的前端flutter app上的对应使用的接口,并且字段是否能对应上,我看见就是我的这个好像有点无法成功的对应上
5. 我接下来希望你能作为一个很严格的代码业务检查官,我要开始检查我的某些业务逻辑的整体的逻辑以及实现,以及是否有冗余代码的实现,你需要考虑全部涉及到我提的这个需求的全部的全部相关代码并且检查是否有就是冲突的逻辑等,可以告知我相关代码以及,如果对于我提的修改意见你能就是反驳我,如果能给出更好的修改意见,我会考虑并是否采纳的
6. 对于的很多文件的修改和注释的话,开头的注释对于这个文件的话,需要你来对于每个文件不同的方法模块生成 //数字序列号:精简的注释

### 开发机器

- **操作系统**: Windows 10 Pro 22H2
- **Python**: 3.11.4
- **依赖**: `python-snap7`, `fastapi`, `influxdb-client`, `pydantic`

### 工控机器

- **操作系统**: Windows 10 IoT Enterprise LTSC 2021
- **Python**: 3.11.4 (venv)
- **依赖**: 同上

我希望在我的开发机部署测试的化,我的目录是PS C:\Users\20216\Documents\GitHub\Clutch\ceramic-electric-furnace-backend> 
我尽量也能不是用docker 启动我的后端,直接python启动部署我的后端服务,这样的化,方便测试,毕竟我的后端也是不通过docker部署到工控机上的.