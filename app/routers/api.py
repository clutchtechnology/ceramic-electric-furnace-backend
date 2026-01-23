# ============================================================
# 文件说明: api.py - API 路由汇总展示
# ============================================================
"""
电炉监控系统 - API 端点汇总

运行本文件可查看所有 API 端点:
    python -m app.routers.api
"""

from fastapi import APIRouter

# 导入所有子路由
from .health import router as health_router
from .furnace import router as furnace_router
from .history import router as history_router
from .alarm import router as alarm_router
from .valve import router as valve_router


# 创建主路由
api_router = APIRouter()

# 注册所有子路由
# 注意: health_router 内部已经包含了 /api 前缀
api_router.include_router(health_router, tags=["Health"])
# furnace_router 需要添加 /api/furnace 前缀
api_router.include_router(furnace_router, prefix="/api/furnace", tags=["Furnace"])
# history_router 需要添加 /api/history 前缀
api_router.include_router(history_router, prefix="/api/history", tags=["History"])
# alarm_router 需要添加 /api/alarm 前缀
api_router.include_router(alarm_router, prefix="/api/alarm", tags=["Alarm"])
# valve_router 需要添加 /api/valve 前缀
api_router.include_router(valve_router, prefix="/api/valve", tags=["Valve"])


# ============================================================
# API 端点汇总 (按业务分类)
# ============================================================
"""
┌─────────────────────────────────────────────────────────────┐
│                   电炉监控系统 API                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  【健康检查】 health.py                                      │
│  └─ GET  /api/health              系统健康检查              │
│                                                             │
│  【电炉业务】 furnace.py                                     │
│  ├─ GET  /api/furnace/list        获取电炉列表              │
│  ├─ GET  /api/furnace/realtime    所有电炉实时数据          │
│  ├─ GET  /api/furnace/realtime/{id} 单个电炉实时数据        │
│  └─ GET  /api/furnace/history     历史趋势查询              │
│                                                             │
│  【蝶阀状态】 valve.py                                       │
│  ├─ GET  /api/valve/status/queues  获取蝶阀状态队列         │
│  ├─ GET  /api/valve/status/latest  获取蝶阀最新状态         │
│  └─ GET  /api/valve/status/statistics  蝶阀状态统计         │
│                                                             │
│  【报警记录】 alarm.py                                       │
│  ├─ POST /api/alarm/record         记录单条报警             │
│  ├─ POST /api/alarm/batch          批量记录报警             │
│  ├─ GET  /api/alarm/list           查询报警列表             │
│  └─ GET  /api/alarm/statistics     报警统计信息             │
│                                                             │
└─────────────────────────────────────────────────────────────┘

文件结构:
    app/routers/
    ├── __init__.py       # 导出 api_router
    ├── api.py            # 路由汇总 (本文件)
    ├── health.py         # 健康检查
    ├── furnace.py        # 电炉业务
    ├── valve.py          # 蝶阀状态
    ├── alarm.py          # 报警记录
    └── history.py        # 历史数据

总计: 13 个 API 端点
"""


def print_api_summary():
    """打印 API 端点汇总"""
    summary = """
╔═══════════════════════════════════════════════════════════════╗
║               电炉监控系统 - API 端点汇总                       ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  【健康检查】                                                  ║
║    GET  /api/health                 系统健康检查              ║
║                                                               ║
║  【电炉业务】 (/api/furnace)                                   ║
║    GET  /api/furnace/list           获取电炉列表              ║
║    GET  /api/furnace/realtime       所有电炉实时数据          ║
║    GET  /api/furnace/realtime/{id}  单个电炉实时数据          ║
║    GET  /api/furnace/history        历史趋势查询              ║
║                                                               ║
║  【蝶阀状态】 (/api/valve)                                     ║
║    GET  /api/valve/status/queues    获取蝶阀状态队列          ║
║    GET  /api/valve/status/latest    获取蝶阀最新状态          ║
║    GET  /api/valve/status/statistics 蝶阀状态统计             ║
║                                                               ║
║  【报警记录】 (/api/alarm)                                     ║
║    POST /api/alarm/record           记录单条报警              ║
║    POST /api/alarm/batch            批量记录报警              ║
║    GET  /api/alarm/list             查询报警列表              ║
║    GET  /api/alarm/statistics       报警统计信息              ║
║                                                               ║
╠═══════════════════════════════════════════════════════════════╣
║  总计: 13 个端点                                               ║
╚═══════════════════════════════════════════════════════════════╝
"""
    print(summary)


if __name__ == "__main__":
    print_api_summary()
