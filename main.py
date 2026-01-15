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
    print("Starting electric furnace backend...")
    
    # 启动轮询服务
    if settings.enable_polling or settings.enable_mock_polling:
        from app.services.polling_service import start_polling
        await start_polling()
    
    yield
    
    # 停止轮询服务
    if settings.enable_polling or settings.enable_mock_polling:
        from app.services.polling_service import stop_polling
        await stop_polling()
    
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

# 注册路由
from app.routers import health, furnace

app.include_router(health.router, tags=["Health"])
app.include_router(furnace.router, prefix="/api/furnace", tags=["Furnace"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.debug,
    )
