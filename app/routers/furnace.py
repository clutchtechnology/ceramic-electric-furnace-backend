"""
电炉后端 - 电炉数据路由
"""
from fastapi import APIRouter, Query
from typing import Optional
from datetime import datetime, timedelta, timezone

from app.core.influxdb import query_data
from app.services.furnace_service import get_realtime_data, get_furnace_list
from app.core.alarm_store import query_alarms

router = APIRouter()


@router.get("/list")
async def list_furnaces():
    """获取所有电炉列表"""
    furnaces = get_furnace_list()
    return {
        "success": True,
        "data": furnaces,
        "error": None
    }


@router.get("/realtime")
async def get_realtime():
    """获取所有电炉实时数据"""
    data = get_realtime_data()
    return {
        "success": True,
        "data": data,
        "error": None
    }


@router.get("/realtime/{furnace_id}")
async def get_furnace_realtime(furnace_id: str):
    """获取单个电炉实时数据"""
    all_data = get_realtime_data()
    furnace_data = next((f for f in all_data if f.get("device_id") == furnace_id), None)
    
    if furnace_data is None:
        return {
            "success": False,
            "data": None,
            "error": f"电炉 {furnace_id} 不存在"
        }
    
    return {
        "success": True,
        "data": furnace_data,
        "error": None
    }


@router.get("/history")
async def get_history(
    furnace_id: Optional[str] = Query(None, description="电炉ID"),
    parameter: str = Query("temperature", description="参数类型: temperature/power/current/voltage"),
    start: Optional[str] = Query(None, description="开始时间 ISO格式"),
    end: Optional[str] = Query(None, description="结束时间 ISO格式"),
    interval: str = Query("1m", description="聚合间隔: 5s/1m/5m/1h/1d")
):
    """查询电炉历史数据"""
    if end is None:
        end_time = datetime.now(timezone.utc)
    else:
        end_time = datetime.fromisoformat(end.replace('Z', '+00:00'))
    
    if start is None:
        start_time = end_time - timedelta(hours=1)
    else:
        start_time = datetime.fromisoformat(start.replace('Z', '+00:00'))
    
    tags = {}
    if furnace_id:
        tags["device_id"] = furnace_id
    
    data = query_data(
        measurement="sensor_data",
        start_iso=start_time.isoformat(),
        stop_iso=end_time.isoformat(),
        tags=tags,
        interval=interval,
        device_id=furnace_id
    )
    
    filtered_data = [d for d in data if d.get("field") == parameter]
    
    return {
        "success": True,
        "data": filtered_data,
        "meta": {
            "furnace_id": furnace_id,
            "parameter": parameter,
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "interval": interval,
            "count": len(filtered_data)
        },
        "error": None
    }


@router.get("/alarms")
async def get_alarms(
    furnace_id: Optional[str] = Query(None, description="电炉ID筛选"),
    level: Optional[str] = Query(None, description="报警级别: warning/alarm"),
    hours: int = Query(24, description="查询时间范围(小时)")
):
    """查询电炉报警记录"""
    start_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    alarms = query_alarms(
        start_time=start_time,
        device_id=furnace_id,
        level=level
    )
    
    return {
        "success": True,
        "data": alarms,
        "error": None
    }
