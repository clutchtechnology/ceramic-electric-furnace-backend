"""
电炉后端 - 历史数据查询路由
支持各模块的历史数据查询和批次号筛选
"""
from fastapi import APIRouter, Query
from typing import Optional, List
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel

from app.core.influxdb import get_influx_client
from config import get_settings

router = APIRouter()
settings = get_settings()


# ============================================================
# 数据模型
# ============================================================
class HistoryDataPoint(BaseModel):
    """历史数据点"""
    time: str
    value: float


class HistoryResponse(BaseModel):
    """历史数据响应"""
    success: bool
    data: List[dict]
    meta: dict
    error: Optional[str] = None


# ============================================================
# 通用查询函数
# ============================================================
def _parse_time_range(start: Optional[str], end: Optional[str], hours: int = 24):
    """解析时间范围"""
    if end is None:
        end_time = datetime.now(timezone.utc)
    else:
        end_time = datetime.fromisoformat(end.replace('Z', '+00:00'))
    
    if start is None:
        start_time = end_time - timedelta(hours=hours)
    else:
        start_time = datetime.fromisoformat(start.replace('Z', '+00:00'))
    
    return start_time, end_time


def _query_history(
    field: str,
    start_time: datetime,
    end_time: datetime,
    interval: str = "1m",
    batch_code: Optional[str] = None,
    measurement: str = "sensor_data"
) -> List[dict]:
    """通用历史数据查询
    
    Args:
        field: 要查询的字段名
        start_time: 开始时间
        end_time: 结束时间
        interval: 聚合间隔 (5s/1m/5m/1h/1d)
        batch_code: 批次号筛选 (可选)
        measurement: 测量名称
    
    Returns:
        历史数据列表
    """
    client = get_influx_client()
    query_api = client.query_api()
    
    # 构建过滤条件
    filters = [f'r["_field"] == "{field}"']
    if batch_code:
        filters.append(f'r["batch_code"] == "{batch_code}"')
    
    filter_str = " and ".join(filters)
    
    # 格式化时间为 RFC3339 格式 (InfluxDB 要求)
    start_str = start_time.strftime('%Y-%m-%dT%H:%M:%SZ')
    stop_str = end_time.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    query = f'''
    from(bucket: "{settings.influx_bucket}")
      |> range(start: {start_str}, stop: {stop_str})
      |> filter(fn: (r) => r["_measurement"] == "{measurement}")
      |> filter(fn: (r) => {filter_str})
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
                    "value": record.get_value(),
                    "field": record.get_field(),
                })
        return data
    except Exception as e:
        print(f"❌ 历史数据查询失败: {e}")
        return []


def _query_batch_codes(
    start_time: datetime,
    end_time: datetime,
    field: Optional[str] = None,
    measurement: str = "sensor_data"
) -> List[str]:
    """查询时间范围内的所有批次号
    
    Args:
        start_time: 开始时间
        end_time: 结束时间
        field: 可选的字段筛选
        measurement: 测量名称
    
    Returns:
        批次号列表 (去重、排序)
    """
    client = get_influx_client()
    query_api = client.query_api()
    
    # 构建字段过滤
    field_filter = ""
    if field:
        field_filter = f'|> filter(fn: (r) => r["_field"] == "{field}")'
    
    # 格式化时间为 RFC3339 格式 (InfluxDB 要求)
    start_str = start_time.strftime('%Y-%m-%dT%H:%M:%SZ')
    stop_str = end_time.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    query = f'''
    from(bucket: "{settings.influx_bucket}")
      |> range(start: {start_str}, stop: {stop_str})
      |> filter(fn: (r) => r["_measurement"] == "{measurement}")
      {field_filter}
      |> filter(fn: (r) => exists r["batch_code"])
      |> keep(columns: ["batch_code"])
      |> distinct(column: "batch_code")
    '''
    
    try:
        result = query_api.query(query)
        batch_codes = set()
        for table in result:
            for record in table.records:
                batch_code = record.values.get("batch_code")
                if batch_code:
                    batch_codes.add(batch_code)
        
        # 过滤不规范的批次号
        # 有效格式: XX-XXXX-XX-XX (如 03-2026-01-23) 或 XXXXXXXX (如 03260123)
        import re
        valid_pattern = re.compile(r'^\d{2}-\d{4}-\d{2}-\d{2}$|^\d{8}$')
        filtered_codes = [bc for bc in batch_codes if valid_pattern.match(bc)]
        
        # 排序：最新的批次在前
        return sorted(filtered_codes, reverse=True)
    except Exception as e:
        print(f"❌ 批次号查询失败: {e}")
        return []


# ============================================================
# 批次号查询接口
# ============================================================
@router.get("/batches")
async def get_batches(
    start: Optional[str] = Query(None, description="开始时间 ISO格式"),
    end: Optional[str] = Query(None, description="结束时间 ISO格式"),
    hours: int = Query(24, description="默认查询时间范围(小时)"),
    field: Optional[str] = Query(None, description="字段筛选 (可选)"),
    prefix: Optional[str] = Query(None, description="批次号前缀筛选: SM(主动冶炼) / SX(被动创建)")
):
    """查询时间范围内的所有批次号
    
    用于前端批次号下拉框
    
    参数说明:
    - prefix: 批次号前缀筛选
      - SM: 仅返回主动开始冶炼的批次 (前端点击"开始冶炼")
      - SX: 仅返回被动创建的批次 (轮询时自动创建)
      - None: 返回所有批次
    
    示例:
    - GET /api/history/batches?hours=24  (最近24小时所有批次)
    - GET /api/history/batches?hours=24&prefix=SM  (最近24小时主动冶炼批次)
    - GET /api/history/batches?hours=24&prefix=SX  (最近24小时被动批次)
    - GET /api/history/batches?start=2026-01-20T00:00:00Z&end=2026-01-21T00:00:00Z
    """
    start_time, end_time = _parse_time_range(start, end, hours)
    
    batch_codes = _query_batch_codes(start_time, end_time, field)
    
    # 按前缀筛选
    if prefix:
        prefix_upper = prefix.upper()
        batch_codes = [bc for bc in batch_codes if bc.upper().startswith(prefix_upper)]
    
    return {
        "success": True,
        "data": batch_codes,
        "meta": {
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "count": len(batch_codes),
            "field": field,
            "prefix": prefix
        },
        "error": None
    }


# ============================================================
# 料仓历史数据接口
# ============================================================
@router.get("/hopper")
async def get_hopper_history(
    type: str = Query("weight", description="数据类型: weight(料仓重量) / feed(投料重量)"),
    start: Optional[str] = Query(None, description="开始时间 ISO格式"),
    end: Optional[str] = Query(None, description="结束时间 ISO格式"),
    hours: int = Query(24, description="默认查询时间范围(小时)"),
    interval: str = Query("1m", description="聚合间隔: 5s/1m/5m/1h/1d"),
    batch_code: Optional[str] = Query(None, description="批次号筛选")
):
    """查询料仓历史数据
    
    数据类型:
    - weight: 料仓总重量 (kg)
    - feed: 投料重量 (kg) - 根据料仓重量变化计算
    
    示例:
    - GET /api/history/hopper?type=weight&hours=12
    - GET /api/history/hopper?type=feed&batch_code=SM20260121-1030
    """
    start_time, end_time = _parse_time_range(start, end, hours)
    
    # 字段映射
    field_map = {
        "weight": "hopper_weight",
        "feed": "feed_weight",  # 投料重量 (需要在 polling_service 中计算)
    }
    
    field = field_map.get(type, "hopper_weight")
    
    data = _query_history(field, start_time, end_time, interval, batch_code)
    
    return {
        "success": True,
        "data": data,
        "meta": {
            "type": type,
            "field": field,
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "interval": interval,
            "batch_code": batch_code,
            "count": len(data)
        },
        "error": None
    }


# ============================================================
# 冷却水历史数据接口
# ============================================================
@router.get("/cooling")
async def get_cooling_history(
    type: str = Query("flow_shell", description="数据类型: flow_shell/flow_cover/pressure_shell/pressure_cover/filter_diff"),
    start: Optional[str] = Query(None, description="开始时间 ISO格式"),
    end: Optional[str] = Query(None, description="结束时间 ISO格式"),
    hours: int = Query(24, description="默认查询时间范围(小时)"),
    interval: str = Query("1m", description="聚合间隔: 5s/1m/5m/1h/1d"),
    batch_code: Optional[str] = Query(None, description="批次号筛选")
):
    """查询冷却水历史数据
    
    数据类型:
    - flow_shell: 炉皮冷却水流速 (m³/h)
    - flow_cover: 炉盖冷却水流速 (m³/h)
    - pressure_shell: 炉皮冷却水压 (MPa)
    - pressure_cover: 炉盖冷却水压 (MPa)
    - filter_diff: 前置过滤器压差 (Pa)
    
    示例:
    - GET /api/history/cooling?type=flow_shell&hours=12
    - GET /api/history/cooling?type=pressure_cover&batch_code=SM20260121-1030
    """
    start_time, end_time = _parse_time_range(start, end, hours)
    
    # 字段映射 (对应 InfluxDB 中的字段名)
    field_map = {
        "flow_shell": "WATER_FLOW_1",      # 炉皮流速
        "flow_cover": "WATER_FLOW_2",      # 炉盖流速
        "pressure_shell": "WATER_PRESS_1", # 炉皮水压
        "pressure_cover": "WATER_PRESS_2", # 炉盖水压
        "filter_diff": "filter_pressure_diff",  # 过滤器压差
    }
    
    field = field_map.get(type)
    if not field:
        return {
            "success": False,
            "data": [],
            "meta": {},
            "error": f"不支持的数据类型: {type}"
        }
    
    data = _query_history(field, start_time, end_time, interval, batch_code)
    
    return {
        "success": True,
        "data": data,
        "meta": {
            "type": type,
            "field": field,
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "interval": interval,
            "batch_code": batch_code,
            "count": len(data)
        },
        "error": None
    }


# ============================================================
# 电炉电流历史数据接口
# ============================================================
@router.get("/current")
async def get_current_history(
    electrodes: str = Query("1,2,3", description="电极编号，逗号分隔 (1/2/3)"),
    start: Optional[str] = Query(None, description="开始时间 ISO格式"),
    end: Optional[str] = Query(None, description="结束时间 ISO格式"),
    hours: int = Query(24, description="默认查询时间范围(小时)"),
    interval: str = Query("1m", description="聚合间隔: 5s/1m/5m/1h/1d"),
    batch_code: Optional[str] = Query(None, description="批次号筛选")
):
    """查询电炉三电极电流历史数据
    
    电极编号:
    - 1: 电极1电流 (A相, I_0)
    - 2: 电极2电流 (B相, I_1)
    - 3: 电极3电流 (C相, I_2)
    
    示例:
    - GET /api/history/current?electrodes=1,2,3&hours=12
    - GET /api/history/current?electrodes=1&batch_code=SM20260121-1030
    """
    start_time, end_time = _parse_time_range(start, end, hours)
    
    # 解析电极编号
    electrode_list = [e.strip() for e in electrodes.split(",")]
    
    # 字段映射
    field_map = {
        "1": "I_0",  # A相电流 -> 电极1
        "2": "I_1",  # B相电流 -> 电极2
        "3": "I_2",  # C相电流 -> 电极3
    }
    
    # 查询每个电极的数据
    result_data = {}
    for electrode in electrode_list:
        field = field_map.get(electrode)
        if field:
            data = _query_history(field, start_time, end_time, interval, batch_code)
            result_data[f"electrode_{electrode}"] = data
    
    return {
        "success": True,
        "data": result_data,
        "meta": {
            "electrodes": electrode_list,
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "interval": interval,
            "batch_code": batch_code,
            "count": {k: len(v) for k, v in result_data.items()}
        },
        "error": None
    }


# ============================================================
# 电炉功率/能耗历史数据接口
# ============================================================
@router.get("/power")
async def get_power_history(
    type: str = Query("power", description="数据类型: power(瞬时功率) / energy(能耗)"),
    start: Optional[str] = Query(None, description="开始时间 ISO格式"),
    end: Optional[str] = Query(None, description="结束时间 ISO格式"),
    hours: int = Query(24, description="默认查询时间范围(小时)"),
    interval: str = Query("1m", description="聚合间隔: 5s/1m/5m/1h/1d"),
    batch_code: Optional[str] = Query(None, description="批次号筛选")
):
    """查询电炉功率/能耗历史数据
    
    数据类型:
    - power: 瞬时功率 (kW)
    - energy: 累计能耗 (kWh)
    
    示例:
    - GET /api/history/power?type=power&hours=12
    - GET /api/history/power?type=energy&batch_code=SM20260121-1030
    """
    start_time, end_time = _parse_time_range(start, end, hours)
    
    # 字段映射
    field_map = {
        "power": "Pt",      # 总功率 (kW)
        "energy": "ImpEp",  # 累计有功电能 (kWh)
    }
    
    field = field_map.get(type, "Pt")
    
    data = _query_history(field, start_time, end_time, interval, batch_code)
    
    return {
        "success": True,
        "data": data,
        "meta": {
            "type": type,
            "field": field,
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "interval": interval,
            "batch_code": batch_code,
            "count": len(data)
        },
        "error": None
    }


# ============================================================
# 批次摘要接口 (用于历史轮次对比柱状图)
# ============================================================
def _query_latest_value(
    field: str,
    batch_code: str,
    measurement: str = "sensor_data"
) -> Optional[float]:
    """查询某批次某字段的最新值（时间戳最靠近当前时间的值）
    
    Args:
        field: 字段名
        batch_code: 批次号
        measurement: 测量名称
    
    Returns:
        最新值，如果查询失败则返回None
    """
    client = get_influx_client()
    query_api = client.query_api()
    
    # 查询该批次的最后一条记录
    query = f'''
    from(bucket: "{settings.influx_bucket}")
      |> range(start: -30d)
      |> filter(fn: (r) => r["_measurement"] == "{measurement}")
      |> filter(fn: (r) => r["_field"] == "{field}")
      |> filter(fn: (r) => r["batch_code"] == "{batch_code}")
      |> last()
    '''
    
    try:
        result = query_api.query(query)
        for table in result:
            for record in table.records:
                return record.get_value()
        return None
    except Exception as e:
        print(f"❌ 查询最新值失败 (field={field}, batch={batch_code}): {e}")
        return None


@router.get("/batch/summary")
async def get_batch_summaries(
    batch_codes: str = Query(..., description="批次号列表，逗号分隔"),
):
    """查询多个批次的摘要数据（用于历史轮次对比柱状图）
    
    返回每个批次的最新值：
    - feed_weight: 投料重量 (kg)
    - shell_water_total: 炉皮冷却水累计用量 (m³)
    - cover_water_total: 炉盖冷却水累计用量 (m³)
    
    示例:
    - GET /api/history/batch/summary?batch_codes=SM20260121-1030,SM20260122-0830
    """
    # 解析批次号列表
    batch_list = [bc.strip() for bc in batch_codes.split(",") if bc.strip()]
    
    if not batch_list:
        return {
            "success": False,
            "data": [],
            "meta": {},
            "error": "批次号列表不能为空"
        }
    
    summaries = []
    for batch_code in batch_list:
        # 查询每个批次的最新值
        # 注意: 这些字段名必须与 InfluxDB 存储的字段名一致
        # - feeding_total: 来自 process_weight_data() -> 'feeding_total'
        # - furnace_shell_water_total: 来自 FurnaceConverter -> 冒号系统累计
        # - furnace_cover_water_total: 来自 FurnaceConverter -> 炉盖系统累计
        feed_weight = _query_latest_value("feeding_total", batch_code)
        shell_water = _query_latest_value("furnace_shell_water_total", batch_code)
        cover_water = _query_latest_value("furnace_cover_water_total", batch_code)
        
        summaries.append({
            "batch_code": batch_code,
            "feed_weight": feed_weight,
            "shell_water_total": shell_water,
            "cover_water_total": cover_water,
        })
    
    return {
        "success": True,
        "data": summaries,
        "meta": {
            "count": len(summaries),
            "batch_codes": batch_list
        },
        "error": None
    }


# ============================================================
# 通用历史数据接口 (灵活查询)
# ============================================================
@router.get("/query")
async def query_history(
    field: str = Query(..., description="字段名 (如: Pt, I_0, hopper_weight)"),
    start: Optional[str] = Query(None, description="开始时间 ISO格式"),
    end: Optional[str] = Query(None, description="结束时间 ISO格式"),
    hours: int = Query(24, description="默认查询时间范围(小时)"),
    interval: str = Query("1m", description="聚合间隔: 5s/1m/5m/1h/1d"),
    batch_code: Optional[str] = Query(None, description="批次号筛选"),
    measurement: str = Query("sensor_data", description="测量名称")
):
    """通用历史数据查询接口
    
    可查询任意字段的历史数据
    
    示例:
    - GET /api/history/query?field=Pt&hours=12
    - GET /api/history/query?field=hopper_weight&batch_code=SM20260121-1030
    """
    start_time, end_time = _parse_time_range(start, end, hours)
    
    data = _query_history(field, start_time, end_time, interval, batch_code, measurement)
    
    return {
        "success": True,
        "data": data,
        "meta": {
            "field": field,
            "measurement": measurement,
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "interval": interval,
            "batch_code": batch_code,
            "count": len(data)
        },
        "error": None
    }
