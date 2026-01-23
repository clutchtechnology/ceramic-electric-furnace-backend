# ============================================================
# 文件说明: alarm.py - 报警记录 API
# ============================================================
"""
电炉监控系统 - 报警记录接口

支持的报警类型:
- arc_current: 电弧电流报警 (1/2/3)
- arc_voltage: 电弧电压报警 (1/2/3)
- distance: 测距报警 (1/2/3)
- pressure: 压力报警
- flow: 流量报警
- water_pressure: 炉皮冷却水水压报警 (1/2)
- filter_pressure_diff: 前置过滤器压差报警 (水压1-水压2)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime, timezone
from enum import Enum

from app.core.influxdb import write_point, query_data, get_influx_client
from config import get_settings

router = APIRouter()
settings = get_settings()


# ============================================================
# 数据模型
# ============================================================

class AlarmType(str, Enum):
    """报警类型枚举"""
    ARC_CURRENT = "arc_current"
    ARC_VOLTAGE = "arc_voltage"
    DISTANCE = "distance"
    PRESSURE = "pressure"
    FLOW = "flow"
    WATER_PRESSURE = "water_pressure"
    FILTER_PRESSURE_DIFF = "filter_pressure_diff"


class AlarmLevel(str, Enum):
    """报警级别"""
    LOW = "low"      # 低位告警
    HIGH = "high"    # 高位告警


class AlarmRecord(BaseModel):
    """报警记录请求模型"""
    alarm_type: AlarmType = Field(..., description="报警类型")
    alarm_level: AlarmLevel = Field(..., description="报警级别 (low/high)")
    device_index: int = Field(default=1, ge=1, le=3, description="设备编号 (1-3)")
    current_value: float = Field(..., description="当前值")
    threshold_value: float = Field(..., description="阈值")
    message: Optional[str] = Field(None, description="报警描述")


class AlarmResponse(BaseModel):
    """报警响应模型"""
    success: bool
    message: str
    alarm_id: Optional[str] = None


class AlarmQueryParams(BaseModel):
    """报警查询参数"""
    start_time: str = Field(..., description="开始时间 (ISO 8601)")
    end_time: str = Field(..., description="结束时间 (ISO 8601)")
    alarm_type: Optional[AlarmType] = Field(None, description="报警类型过滤")
    device_index: Optional[int] = Field(None, description="设备编号过滤")


# ============================================================
# API 端点
# ============================================================

@router.post("/record", response_model=AlarmResponse)
async def create_alarm_record(alarm: AlarmRecord):
    """
    创建报警记录
    
    将报警数据写入 InfluxDB，measurement 为 alarm_logs，tag 为 alarm
    """
    try:
        # 构建报警ID
        timestamp = datetime.now(timezone.utc)
        alarm_id = f"{alarm.alarm_type.value}_{alarm.device_index}_{timestamp.strftime('%Y%m%d%H%M%S%f')}"
        
        # 构建报警消息
        if alarm.message:
            message = alarm.message
        else:
            type_names = {
                AlarmType.ARC_CURRENT: f"电弧{alarm.device_index}电流",
                AlarmType.ARC_VOLTAGE: f"电弧{alarm.device_index}电压",
                AlarmType.DISTANCE: f"测距{alarm.device_index}",
                AlarmType.PRESSURE: "压力",
                AlarmType.FLOW: "流量",
                AlarmType.WATER_PRESSURE: f"冷却水水压{alarm.device_index}",
                AlarmType.FILTER_PRESSURE_DIFF: "前置过滤器压差",
            }
            level_text = "低于下限" if alarm.alarm_level == AlarmLevel.LOW else "超过上限"
            message = f"{type_names.get(alarm.alarm_type, alarm.alarm_type.value)} {level_text}"
        
        # 写入 InfluxDB
        tags = {
            "alarm": "true",  # 固定 tag
            "alarm_type": alarm.alarm_type.value,
            "alarm_level": alarm.alarm_level.value,
            "device_index": str(alarm.device_index),
        }
        
        fields = {
            "alarm_id": alarm_id,
            "current_value": alarm.current_value,
            "threshold_value": alarm.threshold_value,
            "message": message,
        }
        
        success = write_point(
            measurement="alarm_logs",
            tags=tags,
            fields=fields,
            timestamp=timestamp
        )
        
        if success:
            return AlarmResponse(
                success=True,
                message="报警记录已保存",
                alarm_id=alarm_id
            )
        else:
            raise HTTPException(status_code=500, detail="写入数据库失败")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建报警记录失败: {str(e)}")


@router.get("/list")
async def get_alarm_list(
    start_time: str,
    end_time: str,
    alarm_type: Optional[str] = None,
    device_index: Optional[int] = None,
    limit: int = 100
):
    """
    查询报警记录列表
    
    Args:
        start_time: 开始时间 (ISO 8601)
        end_time: 结束时间 (ISO 8601)
        alarm_type: 报警类型过滤 (可选)
        device_index: 设备编号过滤 (可选)
        limit: 返回条数限制
    """
    try:
        client = get_influx_client()
        query_api = client.query_api()
        
        # 构建过滤条件
        filters = ['r["alarm"] == "true"']
        if alarm_type:
            filters.append(f'r["alarm_type"] == "{alarm_type}"')
        if device_index:
            filters.append(f'r["device_index"] == "{device_index}"')
        
        filter_str = " and ".join(filters)
        
        query = f'''
        from(bucket: "{settings.influx_bucket}")
          |> range(start: {start_time}, stop: {end_time})
          |> filter(fn: (r) => r["_measurement"] == "alarm_logs")
          |> filter(fn: (r) => {filter_str})
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> sort(columns: ["_time"], desc: true)
          |> limit(n: {limit})
        '''
        
        result = query_api.query(query)
        
        alarms = []
        for table in result:
            for record in table.records:
                alarms.append({
                    "time": record.get_time().isoformat(),
                    "alarm_type": record.values.get("alarm_type"),
                    "alarm_level": record.values.get("alarm_level"),
                    "device_index": record.values.get("device_index"),
                    "current_value": record.values.get("current_value"),
                    "threshold_value": record.values.get("threshold_value"),
                    "message": record.values.get("message"),
                    "alarm_id": record.values.get("alarm_id"),
                })
        
        return {
            "success": True,
            "data": alarms,
            "count": len(alarms)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询报警记录失败: {str(e)}")


@router.get("/statistics")
async def get_alarm_statistics(
    start_time: str,
    end_time: str
):
    """
    获取报警统计信息
    
    按报警类型统计各类报警数量
    """
    try:
        client = get_influx_client()
        query_api = client.query_api()
        
        query = f'''
        from(bucket: "{settings.influx_bucket}")
          |> range(start: {start_time}, stop: {end_time})
          |> filter(fn: (r) => r["_measurement"] == "alarm_logs")
          |> filter(fn: (r) => r["alarm"] == "true")
          |> group(columns: ["alarm_type"])
          |> count()
        '''
        
        result = query_api.query(query)
        
        statistics = {}
        total = 0
        for table in result:
            for record in table.records:
                alarm_type = record.values.get("alarm_type", "unknown")
                count = record.get_value()
                statistics[alarm_type] = count
                total += count
        
        return {
            "success": True,
            "data": {
                "by_type": statistics,
                "total": total
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取报警统计失败: {str(e)}")


# ============================================================
# 批量报警接口 (用于前端批量上报)
# ============================================================

class BatchAlarmRecord(BaseModel):
    """批量报警记录"""
    alarms: List[AlarmRecord]


@router.post("/batch", response_model=dict)
async def create_batch_alarm_records(batch: BatchAlarmRecord):
    """
    批量创建报警记录
    """
    results = []
    success_count = 0
    fail_count = 0
    
    for alarm in batch.alarms:
        try:
            response = await create_alarm_record(alarm)
            results.append({"alarm_id": response.alarm_id, "success": True})
            success_count += 1
        except Exception as e:
            results.append({"error": str(e), "success": False})
            fail_count += 1
    
    return {
        "success": fail_count == 0,
        "message": f"成功: {success_count}, 失败: {fail_count}",
        "results": results
    }
