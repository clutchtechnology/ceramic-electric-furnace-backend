# ============================================================
# 电炉后端 v1.1.5 部署指南
# ============================================================
# 新增功能:
#   - DB41 数据状态解析修复 (28字节)
#   - 料仓重量 Modbus RTU 读取
#   - 串口网桥后台服务脚本
# ============================================================

## 📦 部署步骤

### 1. 开发机打包

```powershell
# 构建镜像
docker build -t furnace-backend:1.1.5 .

# 导出镜像
docker save -o deploy/1.1.5/furnace-backend_1.1.5.tar furnace-backend:1.1.5

# 复制部署文件
Copy-Item docker-compose.yml deploy/1.1.5/
Copy-Item .env.example deploy/1.1.5/.env
Copy-Item scripts/start_serial_bridge_background.ps1 deploy/1.1.5/
Copy-Item scripts/stop_serial_bridge.ps1 deploy/1.1.5/
Copy-Item scripts/check_serial_bridge_status.ps1 deploy/1.1.5/
```

### 2. 工控机部署

```powershell
# A. 进入部署目录
cd D:\deploy\1.1.5

# B. 停止旧容器
docker rm -f furnace-backend

# C. 加载新镜像
docker load -i furnace-backend_1.1.5.tar

# D. 启动串口网桥 (后台运行)
powershell -ExecutionPolicy Bypass -File start_serial_bridge_background.ps1

# E. 启动后端服务
docker compose up -d

# F. 验证
docker compose logs -f --tail=50 backend
```

### 3. 验证测试

```powershell
# 检查串口网桥状态
powershell -ExecutionPolicy Bypass -File check_serial_bridge_status.ps1

# 测试料仓重量读取
docker exec -it furnace-backend python -c "
from app.tools.operation_modbus_weight_reader import read_hopper_weight
result = read_hopper_weight(port='socket://host.docker.internal:7777', baudrate=19200)
print('Success:', result['success'])
print('Weight:', result['weight'], 'kg')
"

# 测试 DB41 读取
docker exec -it furnace-backend python -c "
from app.plc.plc_manager import get_plc_manager
plc = get_plc_manager()
data, err = plc.read_db(41, 0, 28)
print('DB41 Success:', data is not None)
print('Size:', len(data) if data else 0)
"
```

## ⚙️ 环境变量 (.env)

```ini
# PLC 连接
MOCK_MODE=false
PLC_IP=192.168.1.10

# Modbus RTU (料仓重量)
MODBUS_PORT=socket://host.docker.internal:7777
MODBUS_BAUDRATE=19200

# InfluxDB
INFLUX_URL=http://furnace-influxdb:8086
INFLUX_TOKEN=furnace-token
INFLUX_ORG=furnace
INFLUX_BUCKET=sensor_data
```

## 📡 端口映射

| 服务 | 外部端口 | 内部端口 |
|------|----------|----------|
| Backend API | 8082 | 8080 |
| InfluxDB | 8089 | 8086 |
| 串口网桥 | 7777 | - |

## 🔧 故障排除

### 串口网桥无法启动
```powershell
# 检查 COM1 是否被占用
Get-WmiObject Win32_SerialPort | Select Name, DeviceID, Status

# 手动测试
python -m serial.tools.tcp_serial_redirect -P 7777 COM1 19200
```

### Modbus 读取超时
```powershell
# 检查端口监听
netstat -an | Select-String ":7777"

# 检查 Docker 网络
docker exec -it furnace-backend ping host.docker.internal
```

## 📋 文件清单

```
deploy/1.1.5/
├── furnace-backend_1.1.5.tar    # Docker 镜像
├── docker-compose.yml           # 容器编排
├── .env                         # 环境变量
├── start_serial_bridge_background.ps1  # 启动串口网桥
├── stop_serial_bridge.ps1       # 停止串口网桥
├── check_serial_bridge_status.ps1      # 查看状态
└── README.md                    # 本文件
```
