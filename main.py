# ============================================================
# 电炉监控后端 - FastAPI 入口
# ============================================================

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    print("=" * 60)
    print("🔧 Starting electric furnace backend...")
    print("=" * 60)
    
    # 显示当前模式
    if settings.mock_mode:
        print("🧪 当前模式: Mock (开发/测试环境)")
        print("   - 使用随机生成的模拟数据")
        print("   - 无需 PLC 连接")
    else:
        print("🏭 当前模式: PLC (生产环境)")
        print(f"   - PLC IP: {settings.plc_ip}:{settings.plc_port}")
        print(f"   - Modbus: {settings.modbus_port} @ {settings.modbus_baudrate}")
    
    print("-" * 60)
    print("🚀 轮询服务自动启动模式")
    print("   🔥 DB1 弧流弧压: 5s (默认) -> 点击'开始冶炼'切换到 0.2s")
    print("   📊 DB32 传感器: 5s (固定)")
    print("   📡 DB30/DB41 状态: 5s (固定)")
    print("=" * 60)
    
    # 自动启动三速轮询服务
    from app.services.polling_loops_v2 import start_all_polling_loops
    await start_all_polling_loops()
    
    yield
    
    # ============================================================
    # 应用关闭时的资源清理
    # ============================================================
    
    # 1. 停止轮询服务
    from app.services.polling_loops_v2 import stop_all_polling_loops
    print("正在停止轮询服务...")
    await stop_all_polling_loops()
    
    # 2. 关闭 InfluxDB 客户端连接
    try:
        from app.core.influxdb import get_influx_client
        client = get_influx_client()
        client.close()
        print("✅ InfluxDB 客户端已关闭")
    except Exception as e:
        print(f"⚠️ 关闭 InfluxDB 客户端失败: {e}")
    
    # 3. 断开 PLC 连接
    try:
        from app.plc.plc_manager import get_plc_manager
        plc = get_plc_manager()
        plc.disconnect()
        print("✅ PLC 连接已断开")
    except Exception as e:
        print(f"⚠️ 断开 PLC 连接失败: {e}")

    print("Electric furnace backend stopped.")


app = FastAPI(
    title="电炉监控系统 API",
    description="陶瓷电炉监控后端 - 温度监控、功率监控、报警系统",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由 (使用完整路径导入避免循环导入)
from app.routers.health import router as health_router
from app.routers.furnace import router as furnace_router
from app.routers.history import router as history_router
from app.routers.status import router as status_router
from app.routers.control import router as control_router
from app.routers.valve import router as valve_router
from app.routers.batch import router as batch_router

app.include_router(health_router, tags=["Health"])
app.include_router(furnace_router, prefix="/api/furnace", tags=["Furnace"])
app.include_router(history_router, prefix="/api/history", tags=["History"])
app.include_router(status_router, prefix="/api/status", tags=["Status"])
app.include_router(control_router, prefix="/api/control", tags=["Control"])
app.include_router(valve_router, prefix="/api/valve", tags=["Valve"])  # 蝶阀状态路由
app.include_router(batch_router, tags=["Batch"])  # 批次管理路由


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.debug,
    )
