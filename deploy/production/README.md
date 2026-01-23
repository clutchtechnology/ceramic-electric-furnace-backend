# 电炉后端 - 宿主机直接运行部署说明

## 优点
- ✅ 不需要串口网桥
- ✅ 直接访问 COM1 串口
- ✅ 配置更简单

## 部署步骤

### 步骤 1: 准备代码

从开发机复制整个项目到工控机：
```
D:\deploy\backend\    <- 复制 ceramic-electric-furnace-backend 到这里
```

### 步骤 2: 安装 Python 依赖

```powershell
cd D:\deploy\backend
pip install -r requirements.txt
```

或手动安装：
```powershell
pip install fastapi uvicorn python-snap7 pyserial influxdb-client pydantic-settings pyyaml
```

### 步骤 3: 复制配置文件

```powershell
# 将 .env 文件复制到项目根目录
Copy-Item D:\deploy\production\.env D:\deploy\backend\.env
```

### 步骤 4: 启动 InfluxDB (Docker)

```powershell
# 只运行 InfluxDB 容器
docker run -d ^
  --name furnace-influxdb ^
  -p 8089:8086 ^
  -v D:/docker-data/furnace/influxdb-data:/var/lib/influxdb2 ^
  -v D:/docker-data/furnace/influxdb-config:/etc/influxdb2 ^
  -e DOCKER_INFLUXDB_INIT_MODE=setup ^
  -e DOCKER_INFLUXDB_INIT_USERNAME=admin ^
  -e DOCKER_INFLUXDB_INIT_PASSWORD=admin_password ^
  -e DOCKER_INFLUXDB_INIT_ORG=furnace ^
  -e DOCKER_INFLUXDB_INIT_BUCKET=sensor_data ^
  -e DOCKER_INFLUXDB_INIT_ADMIN_TOKEN=furnace-token ^
  influxdb:2.7
```

### 步骤 5: 启动后端服务

```powershell
cd D:\deploy\backend
python main.py
```

或使用 uvicorn：
```powershell
uvicorn main:app --host 0.0.0.0 --port 8082
```

### 步骤 6: 配置为 Windows 服务 (可选)

使用 NSSM 将后端注册为 Windows 服务：
```powershell
# 下载 NSSM: https://nssm.cc/download
nssm install FurnaceBackend "C:\Python311\python.exe" "D:\deploy\backend\main.py"
nssm set FurnaceBackend AppDirectory "D:\deploy\backend"
nssm start FurnaceBackend
```

## 端口说明

| 服务 | 端口 | 说明 |
|------|------|------|
| Backend API | 8082 | HTTP API |
| InfluxDB | 8089 | 时序数据库 |
| COM1 | - | Modbus RTU 串口 |

## 验证

```powershell
# 测试 API
Invoke-RestMethod -Uri "http://localhost:8082/api/health" | ConvertTo-Json

# 测试实时数据
Invoke-RestMethod -Uri "http://localhost:8082/api/furnace/realtime/batch" | ConvertTo-Json -Depth 5
```
