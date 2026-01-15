"""
电炉后端 - 报警日志存储
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

from app.core.influxdb import write_point, get_influx_client
from config import get_settings

settings = get_settings()

_last_alarms: Dict[str, datetime] = {}
_ALARM_DEDUP_SECONDS = 300


def log_alarm(
    device_id: str,
    alarm_type: str,
    param_name: str,
    value: float,
    threshold: float,
    level: str,
    message: str = ""
) -> bool:
    """记录报警日志到InfluxDB"""
    dedup_key = f"{device_id}_{alarm_type}_{level}"
    now = datetime.now(timezone.utc)
    
    if dedup_key in _last_alarms:
        elapsed = (now - _last_alarms[dedup_key]).total_seconds()
        if elapsed < _ALARM_DEDUP_SECONDS:
            return False
    
    tags = {
        "device_id": device_id,
        "alarm_type": alarm_type,
        "level": level,
    }
    
    fields = {
        "param_name": param_name,
        "value": float(value),
        "threshold": float(threshold),
        "message": message or f"{device_id} {param_name}={value:.2f} 超过阈值 {threshold:.2f}",
        "acknowledged": False,
    }
    
    success = write_point("alarm_logs", tags, fields, now)
    
    if success:
        _last_alarms[dedup_key] = now
        print(f"🚨 报警记录: {device_id} {alarm_type} {level} - {param_name}={value:.2f}")
    
    return success


def query_alarms(
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    device_id: Optional[str] = None,
    level: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """查询报警日志"""
    if start_time is None:
        start_time = datetime.now(timezone.utc) - timedelta(hours=24)
    if end_time is None:
        end_time = datetime.now(timezone.utc)
    
    filters = []
    if device_id:
        filters.append(f'r["device_id"] == "{device_id}"')
    if level:
        filters.append(f'r["level"] == "{level}"')
    
    filter_clause = " and ".join(filters) if filters else "true"
    
    query = f'''
    from(bucket: "{settings.influx_bucket}")
        |> range(start: {start_time.isoformat()}, stop: {end_time.isoformat()})
        |> filter(fn: (r) => r["_measurement"] == "alarm_logs")
        |> filter(fn: (r) => {filter_clause})
        |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        |> sort(columns: ["_time"], desc: true)
        |> limit(n: {limit})
    '''
    
    try:
        client = get_influx_client()
        query_api = client.query_api()
        tables = query_api.query(query, org=settings.influx_org)
        
        results = []
        for table in tables:
            for record in table.records:
                results.append({
                    "timestamp": record.get_time().isoformat(),
                    "device_id": record.values.get("device_id", ""),
                    "alarm_type": record.values.get("alarm_type", ""),
                    "level": record.values.get("level", ""),
                    "param_name": record.values.get("param_name", ""),
                    "value": record.values.get("value", 0),
                    "threshold": record.values.get("threshold", 0),
                    "message": record.values.get("message", ""),
                    "acknowledged": record.values.get("acknowledged", False),
                })
        
        return results
    except Exception as e:
        print(f"查询报警日志失败: {e}")
        return []


def get_alarm_count(hours: int = 24) -> Dict[str, int]:
    """获取报警统计"""
    start_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    alarms = query_alarms(start_time=start_time)
    
    warning_count = sum(1 for a in alarms if a.get("level") == "warning")
    alarm_count = sum(1 for a in alarms if a.get("level") == "alarm")
    
    return {
        "warning": warning_count,
        "alarm": alarm_count,
        "total": len(alarms)
    }
