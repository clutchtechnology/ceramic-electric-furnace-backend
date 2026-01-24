# ============================================================
# 文件说明: valve.py - 蝶阀状态队列 API
# ============================================================
# 功能:
#   1. 获取4个蝶阀的历史状态队列
#   2. 每个队列存储最近100次的开关状态
#   3. 状态格式: "10"(关闭), "01"(打开), "11"(异常), "00"(未知)
#   4. 蝶阀配置管理 (全开/全关时间)
#   5. 蝶阀开度计算 (滑动窗口 + 自动校准) 
# ============================================================

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from datetime import datetime

from app.services.polling_data_processor import get_valve_status_queues
from app.services.valve_config_service import (
    get_valve_config_service,
    get_valve_full_action_times,
)
from app.services.valve_calculator_service import (
    get_valve_calculator_service,
    get_all_valve_openness,
    reset_all_valve_openness,
)

router = APIRouter()


# ============================================================
# 请求/响应模型
# ============================================================
class ValveConfigUpdate(BaseModel):
    """单个蝶阀配置更新"""
    full_open_time: Optional[float] = Field(None, ge=1.0, le=300.0, description="全开时间(秒)")
    full_close_time: Optional[float] = Field(None, ge=1.0, le=300.0, description="全关时间(秒)")


class AllValveConfigUpdate(BaseModel):
    """批量蝶阀配置更新"""
    valve_1: Optional[ValveConfigUpdate] = None
    valve_2: Optional[ValveConfigUpdate] = None
    valve_3: Optional[ValveConfigUpdate] = None
    valve_4: Optional[ValveConfigUpdate] = None


class ValveResetRequest(BaseModel):
    """蝶阀开度重置请求"""
    valve_id: Optional[int] = Field(None, ge=1, le=4, description="蝶阀编号(1-4), 空=全部重置")
    batch_code: Optional[str] = Field(None, description="新批次号")


@router.get("/status/queues", summary="获取蝶阀状态队列")
async def get_valve_queues():
    """获取4个蝶阀的状态队列
    
    Returns:
        {
            "success": true,
            "data": {
                "1": [
                    {
                        "status": "10",
                        "timestamp": "2026-01-21T10:00:00Z",
                        "state_name": "closed"
                    },
                    ...
                ],
                "2": [...],
                "3": [...],
                "4": [...]
            },
            "timestamp": "2026-01-21T10:05:00Z"
        }
    
    状态说明:
        - "10": 关闭 (closed)
        - "01": 打开 (open)
        - "11": 异常 (error) - 同时有关和开信号
        - "00": 未知 (unknown) - 无信号
    """
    try:
        queues = get_valve_status_queues()
        
        # 转换 key 为字符串 (FastAPI JSON 序列化要求)
        queues_str_keys = {str(k): v for k, v in queues.items()}
        
        return {
            "success": True,
            "data": queues_str_keys,
            "timestamp": datetime.now().isoformat(),
            "queue_length": {
                str(k): len(v) for k, v in queues.items()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取蝶阀状态队列失败: {str(e)}")


@router.get("/status/latest", summary="获取蝶阀最新状态")
async def get_latest_valve_status():
    """获取4个蝶阀的最新状态
    
    Returns:
        {
            "success": true,
            "data": {
                "1": {"status": "10", "state_name": "closed", "timestamp": "..."},
                "2": {"status": "01", "state_name": "open", "timestamp": "..."},
                "3": {"status": "10", "state_name": "closed", "timestamp": "..."},
                "4": {"status": "01", "state_name": "open", "timestamp": "..."}
            },
            "timestamp": "2026-01-21T10:05:00Z"
        }
    """
    try:
        queues = get_valve_status_queues()
        
        latest_status = {}
        for valve_id, queue in queues.items():
            if queue:
                # 获取队列最后一个元素 (最新状态)
                latest = queue[-1]
                latest_status[str(valve_id)] = latest
            else:
                # 队列为空，返回未知状态
                latest_status[str(valve_id)] = {
                    "status": "00",
                    "state_name": "unknown",
                    "timestamp": datetime.now().isoformat()
                }
        
        return {
            "success": True,
            "data": latest_status,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取最新蝶阀状态失败: {str(e)}")


@router.get("/status/statistics", summary="获取蝶阀状态统计")
async def get_valve_statistics():
    """获取蝶阀状态统计信息
    
    Returns:
        {
            "success": true,
            "data": {
                "1": {
                    "total_records": 100,
                    "closed_count": 45,
                    "open_count": 50,
                    "error_count": 3,
                    "unknown_count": 2,
                    "closed_percentage": 45.0,
                    "open_percentage": 50.0
                },
                ...
            }
        }
    """
    try:
        queues = get_valve_status_queues()
        
        statistics = {}
        for valve_id, queue in queues.items():
            if not queue:
                statistics[str(valve_id)] = {
                    "total_records": 0,
                    "closed_count": 0,
                    "open_count": 0,
                    "error_count": 0,
                    "unknown_count": 0,
                    "closed_percentage": 0.0,
                    "open_percentage": 0.0
                }
                continue
            
            # 统计各状态数量
            status_counts = {"10": 0, "01": 0, "11": 0, "00": 0}
            for record in queue:
                status = record["status"]
                if status in status_counts:
                    status_counts[status] += 1
            
            total = len(queue)
            statistics[str(valve_id)] = {
                "total_records": total,
                "closed_count": status_counts["10"],
                "open_count": status_counts["01"],
                "error_count": status_counts["11"],
                "unknown_count": status_counts["00"],
                "closed_percentage": round(status_counts["10"] / total * 100, 2) if total > 0 else 0.0,
                "open_percentage": round(status_counts["01"] / total * 100, 2) if total > 0 else 0.0
            }
        
        return {
            "success": True,
            "data": statistics,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取蝶阀统计信息失败: {str(e)}")


# ============================================================
# 蝶阀配置 API
# ============================================================
@router.get("/config", summary="获取蝶阀配置")
async def get_valve_config():
    """获取4个蝶阀的全开/全关时间配置
    
    Returns:
        {
            "success": true,
            "data": {
                "1": {"full_open_time": 30.0, "full_close_time": 30.0, "updated_at": "..."},
                "2": {"full_open_time": 30.0, "full_close_time": 30.0, "updated_at": "..."},
                "3": {"full_open_time": 30.0, "full_close_time": 30.0, "updated_at": "..."},
                "4": {"full_open_time": 30.0, "full_close_time": 30.0, "updated_at": "..."}
            }
        }
    """
    try:
        service = get_valve_config_service()
        configs = service.get_all_configs()
        
        return {
            "success": True,
            "data": {
                str(valve_id): config.to_dict()
                for valve_id, config in configs.items()
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取蝶阀配置失败: {str(e)}")


@router.put("/config/{valve_id}", summary="更新单个蝶阀配置")
async def update_single_valve_config(valve_id: int, config: ValveConfigUpdate):
    """更新单个蝶阀的全开/全关时间配置
    
    Args:
        valve_id: 蝶阀编号 (1-4)
        config: 配置数据
    """
    if valve_id < 1 or valve_id > 4:
        raise HTTPException(status_code=400, detail="蝶阀编号必须在1-4之间")
    
    try:
        service = get_valve_config_service()
        updated = service.update_config(
            valve_id=valve_id,
            full_open_time=config.full_open_time,
            full_close_time=config.full_close_time
        )
        
        return {
            "success": True,
            "message": f"蝶阀{valve_id}配置已更新",
            "data": updated.to_dict(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新蝶阀配置失败: {str(e)}")


@router.put("/config", summary="批量更新蝶阀配置")
async def update_all_valve_config(configs: AllValveConfigUpdate):
    """批量更新蝶阀配置
    
    Request Body:
        {
            "valve_1": {"full_open_time": 30.0, "full_close_time": 30.0},
            "valve_2": {"full_open_time": 35.0, "full_close_time": 35.0},
            ...
        }
    """
    try:
        service = get_valve_config_service()
        
        # 构建更新数据
        update_data = {}
        for i, valve_config in enumerate([configs.valve_1, configs.valve_2, configs.valve_3, configs.valve_4], 1):
            if valve_config:
                config_dict = {}
                if valve_config.full_open_time is not None:
                    config_dict['full_open_time'] = valve_config.full_open_time
                if valve_config.full_close_time is not None:
                    config_dict['full_close_time'] = valve_config.full_close_time
                if config_dict:
                    update_data[i] = config_dict
        
        if not update_data:
            raise HTTPException(status_code=400, detail="未提供有效的配置数据")
        
        updated = service.update_all_configs(update_data)
        
        return {
            "success": True,
            "message": f"已更新{len(update_data)}个蝶阀配置",
            "data": {
                str(valve_id): config.to_dict()
                for valve_id, config in updated.items()
            },
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量更新蝶阀配置失败: {str(e)}")


@router.post("/config/reset", summary="重置蝶阀配置为默认值")
async def reset_valve_config(valve_id: Optional[int] = None):
    """重置蝶阀配置为默认值 (30秒)
    
    Args:
        valve_id: 蝶阀编号 (1-4), 不传则重置全部
    """
    try:
        service = get_valve_config_service()
        service.reset_to_default(valve_id)
        
        return {
            "success": True,
            "message": f"蝶阀{'全部' if valve_id is None else valve_id}配置已重置为默认值",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重置蝶阀配置失败: {str(e)}")


# ============================================================
# 蝶阀开度 API
# ============================================================
@router.get("/openness", summary="获取蝶阀开度")
async def get_valve_openness():
    """获取4个蝶阀的当前开度
    
    Returns:
        {
            "success": true,
            "data": {
                "1": {
                    "valve_id": 1,
                    "openness_percent": 45.5,
                    "current_status": "01",
                    "last_calibration": "full_close",
                    "calibration_time": "2026-01-22T10:00:00Z",
                    "batch_code": "SM20260122-1000"
                },
                ...
            }
        }
    """
    try:
        openness_data = get_all_valve_openness()
        
        return {
            "success": True,
            "data": openness_data,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取蝶阀开度失败: {str(e)}")


@router.get("/openness/{valve_id}", summary="获取单个蝶阀开度")
async def get_single_valve_openness(valve_id: int):
    """获取单个蝶阀的当前开度"""
    if valve_id < 1 or valve_id > 4:
        raise HTTPException(status_code=400, detail="蝶阀编号必须在1-4之间")
    
    try:
        service = get_valve_calculator_service()
        openness = service.get_openness(valve_id)
        
        return {
            "success": True,
            "data": openness.to_dict(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取蝶阀开度失败: {str(e)}")


@router.post("/openness/reset", summary="重置蝶阀开度")
async def reset_valve_openness(request: ValveResetRequest):
    """重置蝶阀开度为0%
    
    Args:
        valve_id: 蝶阀编号 (1-4), 空=全部重置
        batch_code: 新批次号
    """
    try:
        service = get_valve_calculator_service()
        service.reset_openness(
            valve_id=request.valve_id,
            batch_code=request.batch_code
        )
        
        return {
            "success": True,
            "message": f"蝶阀{'全部' if request.valve_id is None else request.valve_id}开度已重置为0%",
            "batch_code": request.batch_code,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重置蝶阀开度失败: {str(e)}")


@router.get("/openness/{valve_id}/queue", summary="获取蝶阀计算队列状态")
async def get_valve_queue_status(valve_id: int):
    """获取蝶阀开度计算队列状态 (调试用)"""
    if valve_id < 1 or valve_id > 4:
        raise HTTPException(status_code=400, detail="蝶阀编号必须在1-4之间")
    
    try:
        service = get_valve_calculator_service()
        queue_status = service.get_queue_status(valve_id)
        
        return {
            "success": True,
            "data": queue_status,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取队列状态失败: {str(e)}")
