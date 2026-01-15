"""
电炉后端 - 健康检查路由
"""
from fastapi import APIRouter

from app.core.influxdb import check_influx_health
from config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("/api/health")
async def health_check():
    """系统健康检查"""
    influx_ok, influx_msg = check_influx_health()
    
    return {
        "status": "healthy" if influx_ok else "degraded",
        "services": {
            "backend": {"status": "running", "port": settings.server_port},
            "influxdb": {"status": "ok" if influx_ok else "error", "message": influx_msg},
        },
        "config": {
            "mock_mode": settings.use_mock_data,
            "polling_enabled": settings.enable_polling or settings.enable_mock_polling,
        }
    }
