# 电炉监控后端

#3电炉后端（FastAPI + InfluxDB + S7-1200 + Modbus RTU）

本 README 聚焦**后端核心需求**与**实现文件定位**，用于团队协作与后续维护。

---

## 1. 架构概览

**核心思路：数据与状态分离 + 配置驱动 + 双速轮询**

数据流概览：

1. PLC/Modbus 数据采集
2. 解析器解析原始字节（配置驱动）
3. 转换为物理量 + 批次号标签
4. 批量写入 InfluxDB（历史）
5. 同步写入内存缓存（实时）
6. API 对外提供实时/历史/状态/报警/阀门队列等接口

---

## 2. 核心需求与实现位置

### 2.1 数据与状态分离

- **数据（写入 InfluxDB）**：DB32 传感器数据、DB1 弧流弧压、Modbus 料仓重量
- **状态（仅缓存）**：DB30 通信状态、DB41 数据状态

实现文件：
- app/services/polling_service.py
- app/plc/parser_config_db32.py
- app/plc/parser_config_db1.py
- app/plc/parser_status_db30.py
- app/plc/parser_status_db41.py

### 2.2 配置驱动（避免硬编码偏移）

所有 PLC 字段偏移/结构以 YAML 配置为准：

- configs/plc_modules.yaml（基础模块定义）
- configs/config_L3_P2_F2_C4_db32.yaml（DB32 结构）
- configs/config_vw_data_db1.yaml（DB1 结构）
- configs/status_L3_P2_F2_C4_db30.yaml（DB30 状态）
- configs/status_db41.yaml（DB41 状态）

实现文件：
- app/plc/parser_config_db32.py
- app/plc/parser_config_db1.py
- app/plc/parser_status_db30.py
- app/plc/parser_status_db41.py

### 2.3 PLC 长连接与自动重连

- 必须保持 PLC 长连接，避免频繁握手
- 支持断线重连、连续错误自愈

实现文件：
- app/plc/plc_manager.py

### 2.4 双速轮询架构（高频 + 常规）

- **高频任务**：DB1 弧流弧压（0.2s）
- **常规任务**：DB32/DB30/DB41/Modbus 重量（2s）
- 批量写入策略：高频 10 次合并写入，常规 5 次合并写入

实现文件：
- app/services/polling_service.py
- app/services/polling_loops.py

### 2.5 手动启动轮询（批次号管理）

- 轮询**不自动启动**，必须由前端调用接口启动
- 批次号统一由前端生成或后端自动生成

实现文件：
- app/routers/control.py
- app/services/polling_service.py
- main.py（生命周期提示）

### 2.6 数据转换与存储

- 将解析后的原始值转换为物理量
- 统一写入 InfluxDB（sensor_data / feeding_records / alarm_logs）

实现文件：
- app/tools/converter_furnace.py
- app/tools/converter_elec_db1.py
- app/core/influxdb.py

### 2.7 料仓重量（Modbus RTU）

- 串口读取 Modbus RTU 净重
- 统一写入 InfluxDB，并提供实时缓存

实现文件：
- app/tools/operation_modbus_weight_reader.py
- app/services/polling_service.py

### 2.8 投料记录计算（批次级）

- 从重量历史中识别投料事件
- 每 20 分钟自动计算并写入 feeding_records

实现文件：
- app/services/feeding_service.py

### 2.9 设备状态查询

- DB30：通信状态
- DB41：数据采集状态

实现文件：
- app/routers/status.py
- app/plc/parser_status_db30.py
- app/plc/parser_status_db41.py

### 2.10 蝶阀状态队列

- 维护 4 个蝶阀最近 100 条状态队列
- 提供统计与最新状态接口

实现文件：
- app/services/polling_service.py
- app/routers/valve.py

### 2.11 报警系统

- 报警写入 InfluxDB
- 支持查询/统计/去重

实现文件：
- app/core/alarm_store.py
- app/routers/alarm.py

---

## 3. 数据块与来源说明

| 数据块 | 用途 | 轮询方式 | 处理方式 | 备注 |
| --- | --- | --- | --- | --- |
| DB32 | 传感器数据（测距/压力/流量/蝶阀） | 2s | 解析 + 写库 + 缓存 | 配置驱动 |
| DB30 | Modbus 通信状态 | 2s | 解析 + 缓存 | 仅状态 |
| DB41 | 数据状态 | 2s | 解析 + 缓存 | 仅状态 |
| DB1 | 弧流弧压 | 0.2s | 解析 + 转换 + 写库 + 缓存 | 高频 |
| Modbus RTU | 料仓重量 | 2s | 读取 + 写库 + 缓存 | 串口 |
| DB33 | 电表数据 | 预留 | 解析器已保留但默认禁用 | 可按需启用 |

---

## 4. API 概览（关键路由）

- **控制轮询**：/api/control/start, /api/control/stop, /api/control/status
- **实时数据**：/api/furnace/realtime, /api/furnace/realtime/batch
- **历史查询**：/api/history/*
- **设备状态**：/api/status/db30, /api/status/db41, /api/status/all
- **蝶阀状态**：/api/valve/status/queues, /api/valve/status/latest
- **报警**：/api/alarm/record, /api/alarm/list, /api/alarm/statistics
- **健康检查**：/api/health, /api/health/plc, /api/health/database

实现文件：
- app/routers/

---

## 5. 快速启动

### Mock 模式（开发测试）

```bash
docker compose --profile mock up -d --build
```

### 真实 PLC 模式（生产环境）

```bash
docker compose --profile production up -d --build
```

启动后需调用：

```
POST /api/control/start
{
    "batch_code": "SM20260122001"
}
```

---

## 6. 端口与配置

| 服务 | 端口 |
| --- | --- |
| 后端 API | 8082 |
| InfluxDB | 8088 |

核心配置文件：
- config.py
- .env

---

## 7. 代码结构速览

```
app/
    core/          # InfluxDB + 报警存储
    plc/           # PLC/状态解析器 + 连接管理
    services/      # 轮询 + 投料计算 + 业务服务
    routers/       # API 路由
    tools/         # 数据转换/Modbus 工具
configs/         # PLC 配置与模块定义
```
