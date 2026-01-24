"""
电炉后端 - InfluxDB 核心模块
"""
# ============================================================
# 【数据库写入说明 - InfluxDB 存储结构】
# ============================================================
# Measurement: sensor_data (统一存储所有传感器数据)
# ============================================================
# Tags (索引字段，用于查询过滤):
#   - device_type: electric_furnace (设备类型)
#   - device_id: furnace_1 / electrode / hopper_1 (设备ID)
#   - module_type: 数据模块类型
#     * electrode_depth: 电极深度
#     * cooling_system: 冷却水系统
#     * cooling_water_total: 冷却水累计
#     * arc_data: 弧流弧压
#     * hopper_weight: 料仓重量
#   - sensor: 传感器标识 (如 electrode_1, cooling_water_in)
#   - metric: 指标类型 (如 pressure, flow)
#   - batch_code: 批次号 (动态，用于追踪冶炼轮次)
# ============================================================
# Fields (数据字段，按 module_type 分类):
# ============================================================
# module_type=electrode_depth (电极深度):
#   - distance_mm: 电极深度 (mm)
#   - high_word: 高字 (原始值)
#   - low_word: 低字 (原始值)
# ============================================================
# module_type=cooling_system, metric=pressure (冷却水压力):
#   - value: 压力值 (kPa)
#   - raw: 原始值
# ============================================================
# module_type=cooling_system, metric=flow (冷却水流量):
#   - value: 流量值 (m³/h)
#   - raw: 原始值
# ============================================================
# module_type=cooling_water_total (冷却水累计):
#   - furnace_shell_water_total: 炉皮累计流量 (m³)
#   - furnace_cover_water_total: 炉盖累计流量 (m³)
# ============================================================
# module_type=arc_data (弧流弧压):
#   - arc_current_U/V/W: 三相弧流 (A)
#   - arc_voltage_U/V/W: 三相弧压 (V)
#   - arc_current_setpoint_U/V/W: 三相弧流设定值 (A) - 仅变化时写入
#   - manual_deadzone_percent: 手动死区百分比 (%) - 仅变化时写入
# ============================================================
# module_type=hopper_weight (料仓重量):
#   - net_weight: 料仓净重 (kg)
#   - feeding_total: 累计投料量 (kg)
#   - is_discharging: 投料状态 (0/1)
# ============================================================
# 【写入策略】
# ============================================================
# 1. DB32 传感器数据:
#    - 轮询间隔: 0.5秒
#    - 批量写入: 30次轮询后写入 (15秒)
#    - 写入条件: 必须有批次号且冶炼状态为running/paused
# ============================================================
# 2. DB1 弧流弧压数据:
#    - 轮询间隔: 5秒(默认) / 0.2秒(冶炼中)
#    - 批量写入: 20次轮询后写入 (4秒)
#    - 写入条件: 必须有批次号且冶炼状态为running/paused
# ============================================================
# 3. 料仓重量数据:
#    - 轮询间隔: 0.5秒
#    - 批量写入: 30次轮询后写入 (15秒)
#    - 写入条件: 必须有批次号且冶炼状态为running/paused
# ============================================================
# 4. 不写入数据库的数据 (仅内存缓存):
#    - DB30 通信状态 (ModbusStatusParser)
#    - DB41 数据状态 (DataStateParser)
#    - 蝶阀开度 (ValveCalculatorService)
# ============================================================
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


# ============================================================
# 1: 客户端管理模块
# ============================================================
@lru_cache()
def get_influx_client() -> InfluxDBClient:
    return InfluxDBClient(url=settings.influx_url, token=settings.influx_token, org=settings.influx_org)


# 别名：兼容旧代码中的 get_influxdb_client 调用
get_influxdb_client = get_influx_client


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


# ============================================================
# 2: 数据写入模块
# ============================================================
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


# ============================================================
# 3: Point 构建模块
# ============================================================
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


# ============================================================
# 4: 数据查询模块
# ============================================================
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
