# 电炉后端 v1.1.6 部署说明 (生产模式)

## 修复内容
- ✅ `get_latest_electricity_data` 未定义问题
- ✅ `get_batch_feeding_total` 参数缺失问题

## 部署步骤

### 步骤 1: 启动串口网桥 (重要！)

**以管理员身份运行 PowerShell**，执行：

```powershell
cd D:\deploy\1.1.6

# 方式 A: 绕过执行策略运行
powershell -ExecutionPolicy Bypass -File .\start_serial_bridge.ps1

# 方式 B: 或者先设置执行策略 (一次性)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\start_serial_bridge.ps1
```

验证网桥状态：
```powershell
powershell -ExecutionPolicy Bypass -File .\check_serial_bridge.ps1
```

### 步骤 2: 清理旧容器

```powershell
docker rm -f furnace-backend furnace-influxdb
```

### 步骤 3: 加载新镜像

```powershell
docker load -i furnace-backend_1.1.6.tar
```

### 步骤 4: 启动服务

```powershell
docker compose up -d
```

### 步骤 5: 查看日志

```powershell
docker compose logs -f --tail=50 backend
```

## 预期输出

正常启动后应该看到：
```
🔧 Starting electric furnace backend...
🏭 当前模式: 生产环境 (PLC + Modbus)
   - PLC: 192.168.1.10:102
   - Modbus: socket://host.docker.internal:7777 @ 19200
✅ DB32 配置解析器初始化...
✅ DB1 解析器初始化...
✅ Modbus RTU 料仓重量读取已启用
```

## 常见问题

### Q: 串口网桥启动失败
检查：
1. COM1 是否被其他程序占用
2. 料仓称重仪表是否连接正常
3. 串口参数是否匹配 (19200 波特率)

### Q: Modbus 读取超时
检查：
1. 串口网桥是否运行 (`check_serial_bridge.ps1`)
2. 网络是否正常 (`telnet localhost 7777`)

### Q: PLC 连接失败
检查：
1. PLC IP 是否正确 (192.168.1.10)
2. 工控机与 PLC 网络是否通

## 端口说明

| 服务 | 端口 | 说明 |
|------|------|------|
| Backend API | 8082 | HTTP API |
| InfluxDB | 8089 | 时序数据库 |
| 串口网桥 | 7777 | COM1 -> TCP |
