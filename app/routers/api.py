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


# 创建主路由
api_router = APIRouter()

# 注册所有子路由
# 注意: health_router 内部已经包含了 /api 前缀
api_router.include_router(health_router, tags=["Health"])
# furnace_router 需要添加 /api/furnace 前缀
api_router.include_router(furnace_router, prefix="/api/furnace", tags=["Furnace"])


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
└─────────────────────────────────────────────────────────────┘

文件结构:
    app/routers/
    ├── __init__.py       # 导出 api_router
    ├── api.py            # 路由汇总 (本文件)
    ├── health.py         # 健康检查
    └── furnace.py        # 电炉业务

总计: 5 个 API 端点
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
╠═══════════════════════════════════════════════════════════════╣
║  总计: 5 个端点                                                ║
╚═══════════════════════════════════════════════════════════════╝
"""
    print(summary)


if __name__ == "__main__":
    print_api_summary()
