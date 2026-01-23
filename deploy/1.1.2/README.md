# 电炉监控系统 - v1.1.2 版本说明

> **发布日期**: 2026-01-21  
> **版本类型**: Bug 修复版本 (PATCH)  
> **部署模式**: 生产模式（默认连接真实 PLC）

---

## 🆕 版本更新内容

### 修复问题

1. **InfluxDB 查询语法错误**
   - 问题：历史数据查询失败，返回 400 错误
   - 原因：Flux 查询语句中 `range()` 函数的时间参数格式错误
   - 修复：添加 `Z` 后缀确保时间格式正确
   ```python
   # 修复前
   |> range(start: {start_time.isoformat()}, stop: {end_time.isoformat()})
   
   # 修复后
   |> range(start: {start_time.isoformat()}Z, stop: {end_time.isoformat()}Z)
   ```
   - 影响：历史曲线页面现在可以正确查询和显示数据

### 配置变更

2. **默认启动模式改为生产模式**
   - **变更**：`docker-compose up -d` 直接启动生产模式（连接真实 PLC）
   - **原因**：工控机应默认使用真实数据，而不是 Mock 数据
   - **影响**：不再需要显式指定 `--profile production`

---

## 🚀 部署指南

### 开发机构建

```powershell
# 1. 进入项目目录
cd ceramic-electric-furnace-backend

# 2. 构建新镜像（包含 bug 修复）
docker build -t furnace-backend:1.1.2 .

# 3. 导出镜像
docker save -o furnace-backend-1.1.2.tar furnace-backend:1.1.2

# 4. 复制到工控机部署目录
# 将 furnace-backend-1.1.2.tar 和 docker-compose.yml 复制到工控机
# D:\deploy\1.1.2\
```

### 工控机部署

```powershell
# 1. 停止旧版本容器
cd D:\deploy\1.1.1
docker-compose down

# 2. 加载新镜像
docker load -i D:\deploy\1.1.2\furnace-backend-1.1.2.tar

# 3. 启动新版本（生产模式 - 默认）
cd D:\deploy\1.1.2
docker-compose up -d

# 4. 验证服务
docker ps
docker logs furnace-backend --tail 50

# 5. 测试 API
curl http://localhost:8082/api/health
curl http://localhost:8082/api/health/plc
curl http://localhost:8082/api/history/hopper?type=weight&start=2026-01-20T00:00:00&end=2026-01-21T23:59:59
```

---

## ⚙️ 启动模式说明

### 生产模式（默认）

```powershell
# 连接真实 PLC，自动轮询数据
cd D:\deploy\1.1.2
docker-compose up -d
```

**特点**:
- ✅ 连接真实 S7-1200 PLC (192.168.1.10)
- ✅ 采集真实传感器数据
- ✅ 数据写入 InfluxDB
- ❌ PLC 无法连接时会报错

### Mock 模式（开发测试）

```powershell
# 使用模拟数据，无需 PLC
cd D:\deploy\1.1.2
docker-compose --profile mock up -d
```

**特点**:
- ✅ 生成模拟传感器数据
- ✅ 无需 PLC 连接
- ✅ 适合前端开发和测试
- ⚠️ 数据非真实采集

---

## 🔌 PLC 连接配置

本版本预配置的 PLC 参数（在 docker-compose.yml 中）：

| 参数 | 值 | 说明 |
|------|-----|------|
| `PLC_IP` | `192.168.1.10` | PLC IP 地址 |
| `PLC_PORT` | `102` | S7 协议端口 |
| `PLC_RACK` | `0` | 机架号 |
| `PLC_SLOT` | `1` | 插槽号 |

**如需修改**，编辑 `docker-compose.yml` 中的环境变量后重启容器：
```powershell
docker-compose restart
```

---

## 🧪 验证 PLC 连接

### 检查后端日志

```powershell
docker logs furnace-backend --tail 100
```

**成功连接的日志**:
```
✅ PLC 连接成功: 192.168.1.10
📊 轮询 #1 - 数据已更新
✅ 批量写入成功: 90 个数据点
```

**连接失败的日志**:
```
❌ PLC 连接失败: Connection refused
⚠️ 降级为 Mock 模式
```

### 测试健康检查

```powershell
curl http://localhost:8082/api/health/plc
```

**成功响应**:
```json
{
  "success": true,
  "data": {
    "connected": true,
    "mode": "real",
    "message": "PLC 已连接"
  }
}
```

**失败响应**:
```json
{
  "success": false,
  "data": {
    "connected": false,
    "mode": "mock",
    "message": "PLC 连接失败，使用 Mock 数据"
  }
}
```

---

## 🐛 常见问题

### 1. 历史曲线显示空数据

**原因**: 之前版本的 bug 导致数据查询失败

**解决**: 升级到 v1.1.2（已修复）

---

### 2. PLC 连接失败

**检查清单**:
- [ ] PLC IP 地址是否正确 (192.168.1.10)
- [ ] 工控机与 PLC 网络是否连通 (`ping 192.168.1.10`)
- [ ] PLC S7 通信端口是否开启 (端口 102)
- [ ] Docker 容器网络配置是否正确

**诊断命令**:
```powershell
# 检查网络连通性
ping 192.168.1.10

# 检查端口连通性
Test-NetConnection -ComputerName 192.168.1.10 -Port 102

# 查看容器日志
docker logs furnace-backend --tail 100
```

---

### 3. 回滚到 Mock 模式

如果 PLC 暂时无法连接，可以临时切换到 Mock 模式：

```powershell
# 停止生产模式
docker-compose down

# 启动 Mock 模式
docker-compose --profile mock up -d
```

---

## 📊 版本对比

| 版本 | 历史查询 | 默认模式 | PLC 连接 |
|------|----------|----------|----------|
| 1.1.0 | ❌ 语法错误 | Mock | 可选 |
| 1.1.1 | ❌ 语法错误 | Mock | 可选 |
| **1.1.2** | ✅ 已修复 | **生产** | **默认** |

---

## 🔄 回滚指南

如需回滚到旧版本：

```powershell
# 停止当前版本
cd D:\deploy\1.1.2
docker-compose down

# 启动旧版本 (Mock 模式)
cd D:\deploy\1.1.1
docker-compose --profile mock up -d
```

---

## 📝 下一步行动

1. **构建镜像**: `docker build -t furnace-backend:1.1.2 .`
2. **导出镜像**: `docker save -o furnace-backend-1.1.2.tar furnace-backend:1.1.2`
3. **复制到工控机**: `D:\deploy\1.1.2\`
4. **部署并验证**: `docker-compose up -d && docker logs -f furnace-backend`

---

**维护人员**: 工控系统开发团队  
**支持联系**: 见项目 README.md
