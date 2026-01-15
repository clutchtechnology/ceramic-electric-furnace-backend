"""
电炉后端 - InfluxDB 核心模块
"""
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone
from functools import lru_cache
import threading

from config import get_settings

settings = get_settings()

# 写入锁
_write_lock = threading.Lock()


@lru_cache()
def get_influx_client() -> InfluxDBClient:
    return InfluxDBClient(url=settings.influx_url, token=settings.influx_token, org=settings.influx_org)


def check_influx_health() -> Tuple[bool, str]:
    """检查 InfluxDB 连接健康状态"""
    try:
        client = get_influx_client()
        health = client.health()
        if health.status == "pass":
            return (True, "InfluxDB 正常")
        return (False, f"InfluxDB 状态: {health.status}")
    except Exception as e:
        return (False, str(e))


def write_point(measurement: str, tags: Dict[str, str], fields: Dict[str, Any], timestamp: Optional[datetime] = None) -> bool:
    """写入单个数据点到 InfluxDB"""
    try:
        client = get_influx_client()
        write_api = client.write_api(write_options=SYNCHRONOUS)
        point = _build_point(measurement, tags, fields, timestamp)
        if point is None:
            return False
        
        with _write_lock:
            write_api.write(bucket=settings.influx_bucket, org=settings.influx_org, record=point)
        return True
    except Exception as e:
        print(f"❌ InfluxDB 写入失败: {e}")
        return False


def write_points_batch(points: List[Point]) -> Tuple[bool, str]:
    """批量写入数据点到 InfluxDB"""
    if not points:
        return (True, "")
    
    try:
        client = get_influx_client()
        write_api = client.write_api(write_options=SYNCHRONOUS)
        
        with _write_lock:
            write_api.write(bucket=settings.influx_bucket, org=settings.influx_org, record=points)
        
        return (True, "")
    except Exception as e:
        return (False, str(e))


def build_point(measurement: str, tags: Dict[str, str], fields: Dict[str, Any], timestamp: Optional[datetime] = None) -> Optional[Point]:
    """构建 InfluxDB Point 对象"""
    return _build_point(measurement, tags, fields, timestamp)


def _build_point(measurement: str, tags: Dict[str, str], fields: Dict[str, Any], timestamp: Optional[datetime] = None) -> Optional[Point]:
    """内部方法：构建 Point 对象"""
    point = Point(measurement)
    
    for k, v in tags.items():
        point = point.tag(k, v)
    
    allow_string = measurement == "alarm_logs"
    
    valid_fields = 0
    for k, v in fields.items():
        if v is None:
            continue
        if isinstance(v, str):
            if not (allow_string or k == "comm_state"):
                continue
        point = point.field(k, v)
        valid_fields += 1
    
    if valid_fields == 0:
        return None
    
    if timestamp:
        if timestamp.tzinfo is None:
            timestamp = timestamp.astimezone(timezone.utc)
        point = point.time(timestamp)
    
    return point


def query_data(
    measurement: str, 
    start_iso: str, 
    stop_iso: str, 
    tags: Optional[Dict[str, str]] = None, 
    interval: str = "1m",
    device_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """查询 InfluxDB 历史数据"""
    client = get_influx_client()
    query_api = client.query_api()
    
    filters = []
    if device_id:
        filters.append(f'r["device_id"] == "{device_id}"')
    if tags:
        for k, v in tags.items():
            filters.append(f'r["{k}"] == "{v}"')
    
    tag_filter = ""
    if filters:
        tag_filter = " |> filter(fn: (r) => " + " and ".join(filters) + ")"

    query = f'''
    from(bucket: "{settings.influx_bucket}")
      |> range(start: {start_iso}, stop: {stop_iso})
      |> filter(fn: (r) => r["_measurement"] == "{measurement}")
      {tag_filter}
      |> aggregateWindow(every: {interval}, fn: mean, createEmpty: false)
      |> yield(name: "mean")
    '''

    try:
        result = query_api.query(query)
        data = []
        for table in result:
            for record in table.records:
                data.append({
                    "time": record.get_time().isoformat(),
                    "field": record.get_field(),
                    "value": record.get_value(),
                    **{k: v for k, v in record.values.items() if not k.startswith("_")}
                })
        return data
    except Exception as e:
        print(f"❌ InfluxDB 查询失败: {e}")
        return []
