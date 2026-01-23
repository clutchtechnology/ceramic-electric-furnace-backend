# 电炉监控系统 - v1.1.3 版本说明

> **发布日期**: 2026-01-22  
> **版本类型**: 功能更新版本  
> **部署模式**: 生产模式（默认连接真实 PLC）

---

## 🆕 版本更新内容

### 本版本更新

（请在此处记录 1.1.3 版本的具体更新内容）

---

## 🚀 部署指南

### 步骤一：开发机构建镜像

```powershell
# 1. 进入项目目录
cd c:\Users\20216\Documents\GitHub\Clutch\ceramic-electric-furnace-backend

# 2. 构建新镜像
docker build -t furnace-backend:1.1.3 .

# 3. 导出镜像为 tar 包
docker save -o deploy/1.1.3/furnace-backend-1.1.3.tar furnace-backend:1.1.3

# 4. 将以下文件复制到工控机 D:\electric\Release\1.1.3\ 目录：
#    - furnace-backend-1.1.3.tar
#    - docker-compose.yml
```

### 步骤二：工控机停止旧服务

```powershell
# 1. 进入当前运行的部署目录
cd D:\electric\Release

# 2. 停止旧版本容器（1.1.1）
docker stop furnace-backend
docker stop furnace-influxdb

# 或者使用 docker-compose down（如果在对应目录）
# cd D:\electric\Release\1.1.1
# docker-compose down
```

### 步骤三：工控机部署新版本

```powershell
# 1. 创建部署目录（如果不存在）
mkdir D:\electric\Release\1.1.3

# 2. 将 tar 包和 docker-compose.yml 复制到该目录后

# 3. 加载新镜像
cd D:\electric\Release\1.1.3
docker load -i furnace-backend-1.1.3.tar

# 4. 启动新版本（生产模式 - 连接真实 PLC）
docker-compose up -d

# 5. 验证服务状态
docker ps
docker logs furnace-backend --tail 50
```

### 步骤四：验证部署

```powershell
# 检查容器状态
docker ps

# 预期输出：
# CONTAINER ID   IMAGE                   COMMAND           PORTS                     NAMES
# xxxxxxxx       furnace-backend:1.1.3   "python main.py"  0.0.0.0:8082->8082/tcp    furnace-backend
# xxxxxxxx       influxdb:2.7            "/entrypoint..."  0.0.0.0:8089->8086/tcp    furnace-influxdb

# 测试 API 健康检查
curl http://localhost:8082/api/health
curl http://localhost:8082/api/health/plc

# 检查后端日志（确认连接真实 PLC）
docker logs furnace-backend --tail 30
# 应该看到：
# - "Connecting to PLC at 192.168.0.1:102"
# - "PLC connected successfully"
# - 没有 "MOCK_MODE" 或 "Mock data" 相关日志
```

---

## ⚙️ 启动模式说明

### 生产模式（默认）

```powershell
# 连接真实 PLC，自动轮询数据
cd D:\electric\Release\1.1.3
docker-compose up -d
```

**特点**:
- ✅ 连接真实 S7-1200 PLC (192.168.0.1)
- ✅ 采集真实传感器数据
- ✅ 数据写入 InfluxDB
- ❌ PLC 无法连接时会报错

---

## 🔧 故障排查

### 1. PLC 连接失败

```powershell
# 检查日志
docker logs furnace-backend --tail 50

# 检查 PLC 网络连通性
ping 192.168.0.1
```

### 2. InfluxDB 连接失败

```powershell
# 检查 InfluxDB 容器状态
docker logs furnace-influxdb --tail 50

# 检查数据目录权限
ls D:\docker-data\furnace\
```

### 3. 端口冲突

```powershell
# 检查端口占用
netstat -ano | findstr "8082"
netstat -ano | findstr "8089"
```

---

## 📋 回滚指南

如果新版本出现问题，可以快速回滚到旧版本：

```powershell
# 1. 停止新版本
cd D:\electric\Release\1.1.3
docker-compose down

# 2. 启动旧版本
cd D:\electric\Release\1.1.1
docker-compose up -d

# 3. 验证
docker ps
```

---

## 📁 部署文件清单

| 文件 | 说明 |
|------|------|
| `docker-compose.yml` | Docker 编排配置 |
| `furnace-backend-1.1.3.tar` | 后端镜像包 |
| `README.md` | 本说明文档 |
