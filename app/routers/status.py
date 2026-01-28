# ============================================================
# 文件说明: status.py - 设备状态 API 路由
# ============================================================
# 提供 DB30 (通信状态) 和 DB41 (数据状态) 的查询接口
# 数据来源: polling_service 的内存缓存
# ============================================================

from fastapi import APIRouter, HTTPException
from typing import Any, Dict, List

from app.services.polling_data_processor import (
    get_latest_status_data,
    get_latest_db41_data,
)

router = APIRouter()


# ============================================================
# DB30 通信状态接口
# ============================================================

@router.get("/db30")
async def get_db30_status() -> Dict[str, Any]:
    """获取 DB30
    
    Returns:
        DB30 通信状态数据 (10个设备的 Done/Busy/Error/Status)
    """
    result = get_latest_status_data()
    
    if not result.get('data'):
        return {
            "success": True,
            "data": None,
            "timestamp": None,
            "message": "暂无 DB30 状态数据，请等待轮询"
        }
    
    return {
        "success": True,
        "data": result['data'],
        "timestamp": result['timestamp']
    }


@router.get("/db30/devices")
async def get_db30_devices() -> Dict[str, Any]:
    """获取 DB30 设备列表及其状态
    
    Returns:
        设备列表 (简化格式，适合前端显示)
    """
    result = get_latest_status_data()
    data = result.get('data', {})
    
    if not data:
        return {
            "success": True,
            "devices": [],
            "summary": {"total": 0, "healthy": 0, "error": 0},
            "timestamp": None,
            "message": "暂无数据"
        }
    
    # 转换为列表格式
    devices_dict = data.get('devices', {})
    devices_list = []
    
    for device_id, status in devices_dict.items():
        devices_list.append({
            "device_id": device_id,
            "device_name": status.get('device_name', ''),
            "plc_name": status.get('plc_name', ''),
            "done": status.get('done', False),
            "busy": status.get('busy', False),
            "error": status.get('error', False),
            "status": status.get('status', 0),
            "status_hex": status.get('status_hex', ''),
            "healthy": status.get('healthy', False),
            "data_device_id": status.get('data_device_id', ''),
            "description": status.get('description', '')
        })
    
    return {
        "success": True,
        "devices": devices_list,
        "summary": data.get('summary', {"total": 0, "healthy": 0, "error": 0}),
        "timestamp": result['timestamp']
    }


# ============================================================
# DB41 数据状态接口
# ============================================================

@router.get("/db41")
async def get_db41_status() -> Dict[str, Any]:
    """获取 DB41 数据状态
    
    Returns:
        DB41 数据状态 (传感器数据采集状态: Error/Status)
    """
    result = get_latest_db41_data()
    
    if not result.get('data'):
        return {
            "success": True,
            "data": None,
            "timestamp": None,
            "message": "暂无 DB41 状态数据，请等待轮询"
        }
    
    return {
        "success": True,
        "data": result['data'],
        "timestamp": result['timestamp']
    }


@router.get("/db41/devices")
async def get_db41_devices() -> Dict[str, Any]:
    """获取 DB41 设备列表及其状态
    
    Returns:
        设备列表 (简化格式，适合前端显示)
    """
    result = get_latest_db41_data()
    data = result.get('data', {})
    
    if not data:
        return {
            "success": True,
            "devices": [],
            "summary": {"total": 0, "healthy": 0, "error": 0},
            "timestamp": None,
            "message": "暂无数据"
        }
    
    # 转换为列表格式
    devices_dict = data.get('devices', {})
    devices_list = []
    
    for device_id, status in devices_dict.items():
        devices_list.append({
            "device_id": device_id,
            "device_name": status.get('device_name', ''),
            "plc_name": status.get('plc_name', ''),
            "error": status.get('error', False),
            "status": status.get('status', 0),
            "status_hex": status.get('status_hex', ''),
            "healthy": status.get('healthy', False),
            "data_device_id": status.get('data_device_id', ''),
            "description": status.get('description', '')
        })
    
    return {
        "success": True,
        "devices": devices_list,
        "summary": data.get('summary', {"total": 0, "healthy": 0, "error": 0}),
        "timestamp": result['timestamp']
    }


# ============================================================
# 合并状态接口 (同时获取 DB30 和 DB41)
# ============================================================

@router.get("/all")
async def get_all_status() -> Dict[str, Any]:
    """获取所有状态数据 (DB30 + DB41)
    
    Returns:
        合并的状态数据
    """
    db30_result = get_latest_status_data()
    db41_result = get_latest_db41_data()
    
    # 计算合并的统计
    db30_summary = db30_result.get('data', {}).get('summary', {"total": 0, "healthy": 0, "error": 0})
    db41_summary = db41_result.get('data', {}).get('summary', {"total": 0, "healthy": 0, "error": 0})
    
    total_summary = {
        "total": db30_summary.get('total', 0) + db41_summary.get('total', 0),
        "healthy": db30_summary.get('healthy', 0) + db41_summary.get('healthy', 0),
        "error": db30_summary.get('error', 0) + db41_summary.get('error', 0)
    }
    
    return {
        "success": True,
        "db30": {
            "data": db30_result.get('data'),
            "timestamp": db30_result.get('timestamp')
        },
        "db41": {
            "data": db41_result.get('data'),
            "timestamp": db41_result.get('timestamp')
        },
        "summary": total_summary
    }
