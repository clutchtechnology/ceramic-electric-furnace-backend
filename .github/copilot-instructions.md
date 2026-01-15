# Ceramic Electric Furnace Backend - AI Coding Guidelines

> **Project Identity**: `ceramic-electric-furnace-backend` (FastAPI + InfluxDB + S7-1200)
> **Role**: AI Assistant for Industrial IoT Backend Development

## 1. 核心架构原则 (Core Principles)

1.  **数据与状态分离 (Data vs Status Separation)**:
    - **Data (DB32)**: 传感器数值，需要高频采样，**存储**到时序数据库 (InfluxDB) 用于历史分析。
    - **Status (DB30)**: 设备运行状态/报警，仅需**缓存**在内存中供实时查询，不需要永久存储 (除非是报警日志)。

2.  **模块化配置 (Module-based Configuration)**:
    - **DRY (Don't Repeat Yourself)**: 基础模块定义在 `configs/plc_modules.yaml`。
    - **引用机制**: 具体设备配置通过 `module_ref` 引用基础模块，仅需定义 `offset`。

3.  **双模轮询 (Dual-Mode Polling)**:
    - **Mock Mode**: 既然没有 PLC，就生成随机数据，保证前端开发不受阻。
    - **PLC Mode**: 使用 `python-snap7` 长连接，具备自动重连机制。

## 2. 数据流架构 (Data Flow Architecture)

```mermaid
graph TD
    PLC[S7-1200 PLC] -->|S7 Protocol| PollingService
    
    subgraph PollingService
        direction TB
        Conn[PLC Manager (Singleton)]
        
        subgraph Parsing
            P_Data[ModbusDataParser (DB32)]
            P_Status[ModbusStatusParser (DB30)]
        end
        
        subgraph Caching
            Cache_Status[Memory Cache (Dict)]
            Buffer_Data[Data Buffer]
        end
    end
    
    PLC -->|DB32 (28 bytes)| P_Data
    PLC -->|DB30 (40 bytes)| P_Status
    
    P_Data --> Buffer_Data
    P_Status --> Cache_Status
    
    Buffer_Data -->|Batch Write (10x)| InfluxDB[(InfluxDB)]
    Cache_Status -->|Read| API[FastAPI Endpoints]
    InfluxDB -->|Query| API
```

## 3. 关键文件结构 (Project Structure)

```text
ceramic-electric-furnace-backend/
├── main.py                           # FastAPI 启动入口
├── config.py                         # 全局配置 (Env, Ports, DB Configs)
├── configs/                          # [核心配置层]
│   ├── plc_modules.yaml              # ★ 基础模块库 (Type Definitions)
│   ├── config_L3_P2_F2_C4.yaml       # ★ 数据块配置 (DB32 Sensors)
│   ├── status_L3_P2_F2_C4.yaml       # ★ 状态块配置 (DB30 Status)
│   └── db_mappings.yaml              # ★ DB块映射表
├── app/
│   ├── plc/                          # [PLC 通信层]
│   │   ├── plc_manager.py            # 单例连接管理器 (Reconnect Logic)
│   │   ├── parser_modbus.py          # DB32 数据解析器
│   │   └── parser_status.py          # DB30 状态解析器
│   ├── services/                     # [业务逻辑层]
│   │   ├── polling_service.py        # 轮询核心 (Polling Loop)
│   │   └── furnace_service.py        # 业务查询逻辑
│   ├── tools/                        # [转换工具]
│   │   └── converter_*.py            # 原始值 -> 物理量转换
│   └── routers/                      # [API 路由]
│       ├── furnace.py                # 业务接口
│       └── monitor.py                # 监控接口 (Status)
└── docker-compose.yml                # 容器编排
```

## 4. 核心实现规范 (Implementation Specs)

### 4.1 配置文件引用规范

**基础定义 (`configs/plc_modules.yaml`)**:
```yaml
modules:
  InfraredDistance:
    size: 4
    fields: [{name: HIGH, type: WORD}, {name: LOW, type: WORD}]
```

**实例化 (`configs/config_*.yaml`)**:
```yaml
modules:
  - name: LENTH_1
    module_ref: InfraredDistance  # 引用名必须匹配
    offset: 0
```

### 4.2 轮询服务规范 (`polling_service.py`)

1.  **单例管理**: 必须从 `app.plc.plc_manager` 获取 `get_plc_manager()`。
2.  **异常隔离**: 解析错误不应中断轮询循环。
3.  **特殊处理**: DB32 的偏移量 28 处 (MBrly) 是写寄存器，解析时必须**跳过**或**忽略**。
4.  **性能优化**: InfluxDB 写入应使用 `write_points_batch` 进行批量提交。

### 4.3 PLC 字节序

- **S7-1200**: Big Endian (大端序)。
- Python 解析: 使用 `struct.unpack('>H', ...)` (WORD), `'>f'` (REAL)。
- **位解析**: Byte 中的 Bit 顺序通常需要注意 (Bit 0 是最低位还是最高位，取决于 PLC 逻辑)。

## 5. API 接口设计

- **Base URL**: `http://localhost:8082`
- **Endpoints**:
    - `GET /api/monitor/realtime`: 返回 DB32 解析后的物理量 (Latest)。
    - `GET /api/monitor/status`: 返回 DB30 解析后的通信状态 (Cached)。
    - `GET /api/furnace/history`: 查询 InfluxDB 历史趋势。

## 6. 部署与运维 (Deployment)

### Docker Compose Profiles

- **Mock 开发**:
  ```bash
  docker compose --profile mock up -d
  ```
- **生产环境**:
  ```bash
  docker compose --profile production up -d
  ```

### 端口映射

| Service  | Port | Internal |
| :--- | :--- | :--- |
| Backend API | **8082** | 8080 |
| InfluxDB | **8088** | 8086 |

## 7. 下一次复用指南 (Replication Guide)

如果需要创建一个新的 PLC 监控项目：

1.  **复制架构**: 复制 `app/` 目录结构。
2.  **定义模块**: 在 `configs/plc_modules.yaml` 中定义新设备的字节结构 (Struct)。
3.  **配置映射**: 创建新的 `config_*.yaml` 映射 PLC 内存地址。
4.  **实现解析**: 继承或修改 `parser_*.py` 以适配新的 config 结构。
5.  **启动服务**: 调整 `docker-compose.yml` 端口，避免冲突。

---

**AI 指令**: 在生成代码时，优先参考 `configs/` 目录下的定义来生成解析逻辑。不要硬编码偏移量，而是读取配置文件的 `offset` 属性。
中文回答我.