# 电炉监控系统部署提示词文档

> **奥卡姆剃刀原则**: 只包含必要信息，避免冗余步骤
> **适用项目**: ceramic-electric-furnace-backend + ceramic-electric_furnace-flutter
> **目标**: 向 AI 描述部署需求时使用本提示词

---

## 📋 部署环境信息

### 工控机目录结构

```
D:\
├── deploy\                             # Docker 后端版本库
│   ├── 1.1.0\                          # 历史版本
│   │   ├── furnace-backend-1.1.0.tar   # Docker 后端镜像
│   │   ├── influxdb-2.7.tar            # InfluxDB 镜像
│   │   ├── docker-compose.yml          # 容器编排配置
│   │   └── README.md                   # 版本说明
│   └── 1.1.1\                          # 当前运行版本
│       ├── furnace-backend-1.1.1.tar
│       ├── docker-compose.yml
│       ├── configs\                    # 配置文件目录
│       └── data\                       # 数据目录
│
├── docker-data\                        # 数据持久化目录 (勿删)
│   └── furnace\
│       ├── influxdb-data\              # InfluxDB 数据
│       └── influxdb-config\            # InfluxDB 配置
│
└── electric\                           # Flutter 前端部署目录
    └── Release\
        ├── ceramic_electric_furnace_flutter.exe  # 主程序
        ├── flutter_windows.dll                   # Flutter 运行时
        ├── window_manager_plugin.dll             # 窗口管理插件
        ├── screen_retriever_windows_plugin.dll   # 屏幕获取插件
        ├── data\                                 # Flutter 资源目录
        │   └── flutter_assets\                   # 静态资源
        └── VC_redist.x64.exe                     # VC++ 运行时安装包
```

### 端口规划 (避免冲突)

| 项目 | 后端端口 | InfluxDB 端口 |
|------|----------|---------------|
| 磨料车间 (workshop) | 8080 | 8086 |
| 料仓 (hopper) | 8081 | 8088 |
| **电炉 (furnace)** | **8082** | **8089** |
| 水泵 (waterpump) | 8083 | 8090 |

### 当前运行服务

```powershell
# Docker 容器状态
CONTAINER ID   IMAGE                    PORTS                     NAMES
xxxxxxxx       furnace-backend:1.1.0    0.0.0.0:8082->8082/tcp    furnace-backend
xxxxxxxx       influxdb:2.7             0.0.0.0:8089->8086/tcp    furnace-influxdb

# 后端 API 地址
http://localhost:8082
```

---

## 🚀 部署提示词模板

### A. Docker 后端更新

**提示词**:

```
我需要部署新版本 Docker 后端到工控机 (电炉项目):

1. 新版本信息:
   - 版本号: {例如 1.1.1}
   - 开发机构建:
     cd ceramic-electric-furnace-backend
     docker build -t furnace-backend:{版本号} .
     docker save -o furnace-backend-{版本号}.tar furnace-backend:{版本号}

2. 工控机部署路径:
   D:\deploy\{版本号}\
   需要包含:
   - furnace-backend-{版本号}.tar
   - docker-compose.yml (更新镜像版本号)
   - README.md (版本说明)

3. 操作流程:
   # 停止旧容器
   docker-compose -f D:\deploy\1.1.0\docker-compose.yml down

   # 加载新镜像
   docker load -i D:\deploy\{版本号}\furnace-backend-{版本号}.tar

   # 启动新容器 (Mock模式)
   docker-compose -f D:\deploy\{版本号}\docker-compose.yml --profile mock up -d

   # 或启动新容器 (生产模式)
   docker-compose -f D:\deploy\{版本号}\docker-compose.yml --profile production up -d

   # 验证服务
   docker ps
   curl http://localhost:8082/api/health

4. 注意事项:
   - InfluxDB 数据在 D:\docker-data\furnace\influxdb-data\ (不会丢失)
   - 旧版本容器仅停止，不删除 (可回滚)
   - 检查端口 8082/8089 是否被占用
```

---

### B. Flutter 前端更新

**提示词**:

```
我需要部署新版本 Flutter 前端到工控机 (电炉项目):

1. 开发机构建:
   cd ceramic-electric_furnace-flutter
   flutter clean
   flutter build windows --release

2. 工控机部署路径:
   D:\electric\Release\

3. 复制文件清单 (从开发机 build\windows\x64\runner\Release\):
   - ceramic_electric_furnace_flutter.exe  # 主程序
   - flutter_windows.dll                   # Flutter 运行时
   - window_manager_plugin.dll             # 窗口管理插件
   - screen_retriever_windows_plugin.dll   # 屏幕获取插件
   - data\                                 # Flutter 资源目录 (整个文件夹)

4. 首次部署额外步骤:
   - 安装 VC++ 运行时: D:\electric\Release\VC_redist.x64.exe
   - 或复制 DLL: 从开发机 C:\Windows\System32\ 复制 msvcp140.dll, vcruntime140.dll, vcruntime140_1.dll

5. 验证:
   - 双击 ceramic_electric_furnace_flutter.exe 启动
   - 检查后端连接状态 (右上角健康指示灯)
   - 确认 API 端口: http://localhost:8082 (在 lib/api/api.dart 中配置)

6. 常见问题:
   - VCRUNTIME140.dll 缺失: 安装 VC_redist.x64.exe
   - 后端不可达: 检查 Docker 容器是否运行 (docker ps)
   - 全屏模式: 默认启动为全屏，按 Alt+F4 退出
```

---

### C. 完整系统部署 (首次或重置)

**提示词**:

```
我需要在新工控机上完整部署电炉监控系统:

1. 前置要求:
   - Windows 10 22H2 (Build 19045) 或更高版本
   - Docker Desktop 已安装并启动
   - 磁盘 D:\ 至少 10GB 可用空间

2. 创建目录结构:
   New-Item -Path "D:\deploy", "D:\docker-data\furnace", "D:\electric\Release" -ItemType Directory -Force

3. Docker 后端:
   a. 复制版本目录到 D:\deploy\{版本号}\
   b. 加载镜像: 
      docker load -i D:\deploy\{版本号}\furnace-backend-{版本号}.tar
      docker load -i D:\deploy\{版本号}\influxdb-2.7.tar
   c. 启动服务: 
      cd D:\deploy\{版本号}
      docker-compose --profile mock up -d

4. Flutter 前端:
   a. 复制 Release 文件夹到 D:\electric\Release\
   b. 安装 VC++ 运行时: D:\electric\Release\VC_redist.x64.exe
   c. 创建桌面快捷方式指向 D:\electric\Release\ceramic_electric_furnace_flutter.exe

5. 验证:
   - 后端健康: curl http://localhost:8082/api/health
   - InfluxDB: http://localhost:8089 (用户名: admin, 密码: admin_password)
   - 前端: 双击 ceramic_electric_furnace_flutter.exe

6. 环境变量说明:
   - USE_MOCK_DATA=true: 使用模拟数据 (无PLC时)
   - USE_MOCK_DATA=false + USE_REAL_PLC=true: 连接真实PLC
```

---

## 🔧 快捷命令参考

### Docker 开发机构建

```powershell
# 进入项目目录
cd ceramic-electric-furnace-backend

# 构建镜像
docker build -t furnace-backend:1.1.0 .

# 导出镜像
docker save -o furnace-backend-1.1.0.tar furnace-backend:1.1.0

# 导出 InfluxDB 镜像 (首次部署需要)
docker pull influxdb:2.7
docker save -o influxdb-2.7.tar influxdb:2.7

# 准备部署包
mkdir D:\deploy\1.1.0
copy furnace-backend-1.1.0.tar D:\deploy\1.1.0\
copy influxdb-2.7.tar D:\deploy\1.1.0\
copy docker-compose.yml D:\deploy\1.1.0\
```

### 工控机容器管理

```powershell
# 进入部署目录
cd D:\deploy\1.1.0

# 查看运行状态
docker ps

# 查看日志 (实时)
docker logs -f furnace-backend

# 停止服务
docker-compose down

# 启动服务 (Mock 模式 - 开发测试)
docker-compose --profile mock up -d

# 启动服务 (生产模式 - 连接真实PLC)
docker-compose --profile production up -d

# 重启容器
docker-compose restart

# 查看资源占用
docker stats
```

---

## ❗ 常见问题排查

### 问题 1: Docker Desktop 安装失败

**错误信息**: `Prerequisite failed: incompatible version of Windows`

**解决方案**:
```powershell
# 检查 Windows 版本
winver

# 需要 Windows 10 Build 19045 (22H2) 或更高
# 如果版本过低，升级系统或下载旧版 Docker Desktop (4.25.x)
```

### 问题 2: 后端无法连接 InfluxDB

**检查步骤**:
```powershell
# 1. 检查 InfluxDB 是否运行
docker ps | Select-String "furnace-influxdb"

# 2. 测试 InfluxDB 端口
Test-NetConnection -ComputerName localhost -Port 8089

# 3. 查看 InfluxDB 日志
docker logs furnace-influxdb --tail 50
```

### 问题 3: 端口冲突

**检查步骤**:
```powershell
# 检查端口占用
netstat -ano | Select-String "8082"
netstat -ano | Select-String "8089"

# 如果有其他进程占用，修改 docker-compose.yml 中的端口映射
```

### 问题 4: 容器启动后立即退出

**检查步骤**:
```powershell
# 查看详细错误
docker logs furnace-backend

# 常见原因:
# 1. Python 依赖缺失
# 2. 配置文件路径错误
# 3. InfluxDB 未就绪
```

### 问题 5: Flutter 前端 VCRUNTIME140.dll 缺失

**错误信息**: `找不到 VCRUNTIME140.dll / MSVCP140.dll`

**解决方案**:
```powershell
# 方案 A: 安装 VC++ 运行时
D:\electric\Release\VC_redist.x64.exe /install /quiet

# 方案 B: 复制 DLL 文件
# 从其他正常电脑的 C:\Windows\System32\ 复制以下文件到 D:\electric\Release\:
# - msvcp140.dll
# - vcruntime140.dll
# - vcruntime140_1.dll
```

### 问题 6: Flutter 前端显示"服务不可达"

**检查步骤**:
```powershell
# 1. 确认后端运行中
docker ps | Select-String "furnace-backend"

# 2. 测试后端健康检查
curl http://localhost:8082/api/health
curl http://localhost:8082/api/health/plc
curl http://localhost:8082/api/health/database

# 3. 检查防火墙
netsh advfirewall firewall add rule name="Electric Furnace App" dir=in action=allow program="D:\electric\Release\ceramic_electric_furnace_flutter.exe" enable=yes

# 4. 确认前端 API 端口配置 (lib/api/api.dart)
# static const String baseUrl = 'http://localhost:8082';
```

### 问题 7: Flutter 前端未更新到最新版本

**解决方案**:
```powershell
# 开发机重新构建
cd ceramic-electric_furnace-flutter
flutter clean
flutter build windows --release

# 复制整个 Release 文件夹覆盖工控机的 D:\electric\Release\
```

---

## 📝 版本命名规范

### 语义化版本号

```
格式: MAJOR.MINOR.PATCH

MAJOR: 重大架构变更 (不兼容旧版本)
MINOR: 新功能添加 (向后兼容)
PATCH: Bug 修复 (向后兼容)

示例:
1.0.0  - 初始版本
1.1.0  - 新增电表数据采集
1.1.1  - 修复数据解析 Bug
2.0.0  - 重构为微服务架构
```

### 部署目录命名

```
D:\deploy\
├── 1.0.0\     # 首个生产版本
├── 1.1.0\     # 当前稳定版本
└── 1.2.0\     # 待部署版本 (测试中)
```

---

## 🎯 AI 助手快速指令

### 指令 1: 构建新版本部署包

```
请帮我构建电炉后端版本 {X.Y.Z} 的部署包:
1. Docker 镜像构建命令
2. 准备 deploy/{X.Y.Z}/ 目录的文件清单
3. 生成版本 README.md 说明文件
4. 更新 docker-compose.yml 中的镜像版本号
```

### 指令 2: 生成部署脚本

```
请生成 PowerShell 部署脚本 (deploy_furnace_v{X.Y.Z}.ps1):
- 自动停止旧版本
- 加载新 Docker 镜像
- 启动新容器
- 验证服务启动
- 输出部署报告
```

### 指令 3: 回滚到旧版本

```
需要将电炉后端回滚到版本 {X.Y.Z}:
1. 停止当前容器命令
2. 启动旧版本容器命令
3. 验证回滚成功
```

### 指令 4: 构建 Flutter 前端

```
请帮我构建电炉 Flutter 前端并准备部署:
1. flutter clean && flutter build windows --release
2. 复制 build\windows\x64\runner\Release\ 到工控机 D:\electric\Release\
3. 验证前端启动和后端连接
```

### 指令 5: 调试前端连接问题

```
我的电炉 Flutter 前端显示"服务不可达"，后端健康检查正常:
1. 确认 API 端口配置 (lib/api/api.dart)
2. 重新构建前端 (flutter clean && flutter build windows --release)
3. 复制最新 Release 文件夹到工控机
4. 检查防火墙规则
```

---

## 📌 关键路径速查

| 项目 | 路径 |
|------|------|
| **Docker 后端版本库** | `D:\deploy\{版本号}\` |
| **数据持久化** | `D:\docker-data\furnace\` |
| **Flutter 前端** | `D:\electric\Release\` |
| **后端 API** | `http://localhost:8082` |
| **InfluxDB** | `http://localhost:8089` |
| **开发机后端** | `ceramic-electric-furnace-backend\` |
| **开发机前端** | `ceramic-electric_furnace-flutter\` |

### 关键文件速查

| 文件 | 用途 |
|------|------|
| `D:\electric\Release\ceramic_electric_furnace_flutter.exe` | Flutter 主程序 |
| `D:\deploy\{版本号}\docker-compose.yml` | Docker 编排配置 |
| `lib/api/api.dart` | 前端 API 端口配置 |
| `lib/main.dart` | 前端窗口/全屏配置 |

### InfluxDB 认证信息

| 配置项 | 值 |
|--------|-----|
| URL | http://localhost:8089 |
| 用户名 | admin |
| 密码 | admin_password |
| 组织 | furnace |
| Bucket | sensor_data |
| Token | furnace-token |

---

## 🔌 PLC 配置参考

### S7-1200 连接参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| IP | 192.168.1.10 | PLC IP 地址 |
| Port | 102 | S7 协议端口 |
| Rack | 0 | 机架号 |
| Slot | 1 | 插槽号 |

### DB 块配置

| DB块 | 编号 | 大小 | 用途 |
|------|------|------|------|
| DB32 | 32 | 28 bytes | 传感器数据 (红外测距等) |
| DB30 | 30 | 40 bytes | 通信状态 |
| DB33 | 33 | 56 bytes | 电表数据 |

---

**最后更新**: 2026-01-21  
**维护者**: 工控系统开发团队  
**版本**: v1.1

> **更新日志**:
> - v1.1 (2026-01-21): 添加 Flutter 前端部署章节，完善目录结构，新增常见问题 5-7
> - v1.0: 初始版本，仅包含 Docker 后端部署
