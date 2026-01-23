# ============================================================
# 文件说明: health.py - 健康检查路由
# ============================================================
# 接口列表:
# 1. GET /api/health          - 系统健康检查
# 2. GET /api/health/plc      - PLC连接状态
# 3. GET /api/health/database - 数据库连接状态
# ============================================================

from fastapi import APIRouter
from datetime import datetime

from app.core.influxdb import check_influx_health
from app.plc.plc_manager import get_plc_manager, SNAP7_AVAILABLE
from config import get_settings

router = APIRouter(prefix="/api", tags=["health"])
settings = get_settings()


def _api_response(success: bool, data: dict = None, message: str = None):
    """统一响应格式"""
    return {
        "success": success,
        "data": data,
        "message": message,
        "timestamp": datetime.now().isoformat()
    }


# ------------------------------------------------------------
# 1. GET /health - 系统健康检查
# ------------------------------------------------------------
@router.get("/health")
async def health_check():
    """系统健康检查"""
    return _api_response(True, {
        "status": "healthy",
        "version": "1.0.0"
    })


# ------------------------------------------------------------
# 2. GET /health/plc - PLC连接状态
# ------------------------------------------------------------
@router.get("/health/plc")
async def plc_health():
    """PLC连接状态检查
    
    Returns:
        connected: PLC是否连接
        snap7_available: snap7库是否可用
    """
    try:
        plc = get_plc_manager()
        status = plc.get_status()
        
        # Mock 模式下 PLC 视为连接正常
        if settings.mock_mode:
            return _api_response(True, {
                "connected": True,
                "mode": "mock",
                "message": "Mock 模式运行中"
            })
        
        return _api_response(True, {
            "connected": status["connected"],
            "plc_ip": status["ip"],
            "plc_port": status["port"],
            "rack": status["rack"],
            "slot": status["slot"],
            "snap7_available": SNAP7_AVAILABLE,
            "last_read_time": status["last_read_time"],
            "last_error": status["last_error"],
            "message": "PLC连接正常" if status["connected"] else "PLC未连接"
        })
    except Exception as e:
        return _api_response(False, {
            "connected": False,
            "snap7_available": SNAP7_AVAILABLE
        }, f"PLC状态检查失败: {str(e)}")


# ------------------------------------------------------------
# 3. GET /health/database - 数据库连接状态
# ------------------------------------------------------------
@router.get("/health/database")
async def database_health():
    """数据库连接状态检查"""
    status = {
        "influxdb": {"connected": False}
    }
    
    # 检查InfluxDB
    try:
        influx_ok, influx_msg = check_influx_health()
        status["influxdb"]["connected"] = influx_ok
        if not influx_ok:
            status["influxdb"]["error"] = influx_msg
    except Exception as e:
        status["influxdb"]["error"] = str(e)
    
    all_healthy = all(db["connected"] for db in status.values())
    
    return _api_response(True, {
        "status": "healthy" if all_healthy else "degraded",
        "databases": status
    })
