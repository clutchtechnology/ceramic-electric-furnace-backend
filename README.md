# 电炉监控后端

陶瓷电炉监控系统后端 - FastAPI + InfluxDB + S7-1200 PLC

## 快速启动

### Mock 模式 (开发测试)

```bash
docker compose --profile mock up -d --build
```

### 真实 PLC 模式 (生产环境)

```bash
docker compose --profile production up -d --build
```

## API 端点

### 健康检查

```
GET /api/health
```

### 电炉数据

```
GET /api/furnace/list              # 获取电炉列表
GET /api/furnace/realtime          # 所有电炉实时数据
GET /api/furnace/realtime/{id}     # 单个电炉实时数据
GET /api/furnace/history           # 历史数据查询
GET /api/furnace/alarms            # 报警记录
```

## 项目结构

```
├── main.py                    # FastAPI 入口
├── config.py                  # 配置管理
├── docker-compose.yml         # Docker 配置
├── Dockerfile
├── app/
│   ├── core/
│   │   ├── influxdb.py        # InfluxDB 操作
│   │   └── alarm_store.py     # 报警存储
│   ├── routers/
│   │   ├── health.py          # 健康检查路由
│   │   └── furnace.py         # 电炉数据路由
│   └── services/
│       ├── furnace_service.py # 电炉业务逻辑
│       └── polling_service.py # 轮询服务
└── configs/
    ├── config_furnaces.yaml   # 电炉配置
    ├── plc_modules.yaml       # PLC 模块定义
    └── db_mappings.yaml       # DB 块映射
```

## 端口分配

| 服务          | 端口 |
| ------------- | ---- |
| 后端 API      | 8082 |
| InfluxDB      | 8088 |

## 与其他项目的端口对照

| 项目              | API 端口 | InfluxDB 端口 |
| ----------------- | -------- | ------------- |
| ceramic-workshop  | 8080     | 8086          |
| ceramic-waterpump | 8081     | 8087          |
| ceramic-furnace   | 8082     | 8088          |
