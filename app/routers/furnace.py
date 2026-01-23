"""
电炉后端 - 电炉数据路由
"""
from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta, timezone

from app.core.influxdb import query_data
from app.services.furnace_service import get_realtime_data, get_furnace_list
from app.services.polling_data_processor import (
    get_latest_arc_data,
    get_latest_weight_data,
    get_latest_modbus_data,
    get_latest_electricity_data,
)
from app.services.polling_service import (
    get_batch_info,
    get_polling_stats,
)
from app.services.feeding_service import (
    get_batch_feeding_total,
    get_cached_feeding_total,
    get_batch_feeding_records,
)
from app.services.feeding_accumulator import get_feeding_accumulator
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


@router.get("/debug/modbus")
async def debug_modbus():
    """调试接口：获取原始 Modbus 数据"""
    data = get_latest_modbus_data()
    return {
        "success": True,
        "data": data,
        "keys": list(data.get('data', {}).keys()) if data.get('data') else []
    }


# ============================================================
# 实时数据批量接口 (供前端一次性获取所有数据)
# 注意: 必须在 /realtime/{furnace_id} 之前定义，否则 "batch" 会被当作 furnace_id
# ============================================================

# ============================================================
# 🔥 快速接口: 弧流弧压 (0.2s 轮询)
# ============================================================
@router.get("/realtime/arc")
async def get_realtime_arc():
    """获取弧流弧压实时数据（快速接口，0.2s轮询）
    
    专为高频刷新设计，返回最小数据集:
    - arc_current: 三相弧流 (U/V/W) 及设定值
    - arc_voltage: 三相弧压 (U/V/W)
    - setpoints: 三相设定值 (U/V/W)
    - manual_deadzone_percent: 手动死区百分比
    """
    arc_result = get_latest_arc_data()
    arc_data = arc_result.get('data', {})
    
    arc_current = arc_data.get('arc_current', {})
    arc_voltage = arc_data.get('arc_voltage', {})
    setpoints = arc_data.get('setpoints', {})
    
    return {
        "success": True,
        "data": {
            "arc_current": {
                "U": arc_current.get('U', 0.0),
                "V": arc_current.get('V', 0.0),
                "W": arc_current.get('W', 0.0),
            },
            "arc_voltage": {
                "U": arc_voltage.get('U', 0.0),
                "V": arc_voltage.get('V', 0.0),
                "W": arc_voltage.get('W', 0.0),
            },
            "setpoints": {
                "U": setpoints.get('U', 0.0),
                "V": setpoints.get('V', 0.0),
                "W": setpoints.get('W', 0.0),
            },
            "manual_deadzone_percent": arc_data.get('manual_deadzone_percent', 0.0),
            "timestamp": arc_result.get('timestamp'),
        },
        "error": None
    }


# ============================================================
# 📊 慢速接口: 传感器数据 (0.5s 轮询)
# ============================================================
@router.get("/realtime/sensor")
async def get_realtime_sensor():
    """获取传感器实时数据（慢速接口，0.5s轮询）
    
    返回:
    - electrode_depths: 三个电极深度 (mm)
    - valve_status: 四个蝶阀状态 (开/关/停)
    - valve_openness: 四个蝶阀开度 (%)
    - cooling: 冷却水数据 (流速/水压/累计流量/过滤器压差)
    - hopper: 料仓重量和投料总量
    """
    from app.services.valve_calculator_service import get_all_valve_openness
    
    modbus_result = get_latest_modbus_data()
    weight_result = get_latest_weight_data()
    batch_result = get_batch_info()
    
    modbus_data = modbus_result.get('data', {})
    weight_data = weight_result.get('data', {})
    
    # 电极深度
    electrode_depths = modbus_data.get('electrode_depths', {})
    
    # 辅助函数
    def extract_depth(depth_data):
        if isinstance(depth_data, dict):
            return depth_data.get('distance', 0)
        return depth_data or 0
    
    def extract_flow(flow_data):
        if isinstance(flow_data, dict):
            return flow_data.get('flow', 0)
        return flow_data or 0
    
    def extract_pressure(pressure_data):
        if isinstance(pressure_data, dict):
            return pressure_data.get('pressure', 0)
        return pressure_data or 0
    
    # 蝶阀状态和开度
    try:
        valve_openness = get_all_valve_openness()
    except:
        valve_openness = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}
    
    # 蝶阀状态
    valve_status_data = modbus_data.get('valve_status', {})
    valve_status_byte = valve_status_data.get('raw_byte', 0)
    valve_statuses = {}
    for valve_id in range(1, 5):
        bit_offset = (valve_id - 1) * 2
        bit_close = (valve_status_byte >> bit_offset) & 0x01
        bit_open = (valve_status_byte >> (bit_offset + 1)) & 0x01
        valve_statuses[valve_id] = f"{bit_close}{bit_open}"
    
    # 冷却水
    cooling_pressures = modbus_data.get('cooling_pressures', {})
    cooling_flows = modbus_data.get('cooling_flows', {})
    
    # 投料总量 - 从投料累计器获取（实时累计重量变化）
    feeding_accumulator = get_feeding_accumulator()
    feeding_total_kg = feeding_accumulator.get_feeding_total()
    
    return {
        "success": True,
        "data": {
            # 电极深度
            "electrode_depths": {
                "1": extract_depth(electrode_depths.get('LENTH1')),
                "2": extract_depth(electrode_depths.get('LENTH2')),
                "3": extract_depth(electrode_depths.get('LENTH3')),
            },
            # 蝶阀状态: "01"(开), "10"(关), "00"(停)
            "valve_status": valve_statuses,
            # 蝶阀开度 (%)
            "valve_openness": valve_openness,
            # 冷却水
            "cooling": {
                "furnace_shell": {
                    "flow_m3h": extract_flow(cooling_flows.get('WATER_FLOW_1')),
                    "pressure_kPa": extract_pressure(cooling_pressures.get('WATER_PRESS_1')) * 1000,
                    "total_m3": modbus_data.get('furnace_shell_total_volume', 0.0),
                },
                "furnace_cover": {
                    "flow_m3h": extract_flow(cooling_flows.get('WATER_FLOW_2')),
                    "pressure_kPa": extract_pressure(cooling_pressures.get('WATER_PRESS_2')) * 1000,
                    "total_m3": modbus_data.get('furnace_cover_total_volume', 0.0),
                },
                # 进出口压差 = 炉皮水压 - 炉盖水压 (kPa)
                "filter_pressure_diff_kPa": (extract_pressure(cooling_pressures.get('WATER_PRESS_1')) - extract_pressure(cooling_pressures.get('WATER_PRESS_2'))) * 1000,
            },
            # 料仓
            "hopper": {
                "weight_kg": weight_data.get('weight', 0),
                "feeding_total_kg": feeding_total_kg,
                "success": weight_data.get('success', False),
            },
            # 批次信息
            "batch": batch_result,
            "timestamp": modbus_result.get('timestamp'),
        },
        "error": None
    }


@router.get("/realtime/batch")
async def get_realtime_batch():
    """获取所有实时数据（批量接口）
    
    返回前端需要的所有实时数据:
    - electrodes: 三个电极数据 (深度mm, 电流kA, 电压V)
    - electricity: 电表数据 (功率kW, 能耗kWh, 三相电流A, 三相电压V)
    - cooling: 冷却水数据 (压力MPa, 流量m³/h, 过滤器压差)
    - hopper: 料仓数据 (重量kg, 投料总量kg)
    - batch: 当前批次信息
    
    数据来源:
    - DB32: 红外测距、压力、流量
    - DB33: 电表
    - Modbus RTU: 料仓重量
    - InfluxDB: 投料记录 (feeding_records)
    """
    # 获取各数据源的最新数据
    modbus_result = get_latest_modbus_data()
    electricity_result = get_latest_electricity_data()
    arc_result = get_latest_arc_data()  # DB1 弧流弧压
    weight_result = get_latest_weight_data()
    batch_result = get_batch_info()
    
    modbus_data = modbus_result.get('data', {})
    electricity_data = electricity_result.get('data', {})
    arc_data = arc_result.get('data', {})  # DB1 弧流弧压数据
    weight_data = weight_result.get('data', {})
    
    # 获取当前批次的投料总量 - 从投料累计器获取（实时累计重量变化）
    feeding_accumulator = get_feeding_accumulator()
    feeding_total_kg = feeding_accumulator.get_feeding_total()
    
    # 解析 DB32 传感器数据
    # 红外测距 (电极深度)
    electrode_depths = modbus_data.get('electrode_depths', {})
    # 压力计
    cooling_pressures = modbus_data.get('cooling_pressures', {})
    # 流量计
    cooling_flows = modbus_data.get('cooling_flows', {})
    
    # 辅助函数：提取嵌套数据中的实际值
    def extract_depth(depth_data):
        """提取深度数据：可能是数值或 {'distance': float} 结构"""
        if isinstance(depth_data, dict):
            return depth_data.get('distance', 0)
        return depth_data or 0
    
    def extract_flow(flow_data):
        """提取流量数据：可能是数值或 {'flow': float} 结构"""
        if isinstance(flow_data, dict):
            return flow_data.get('flow', 0)
        return flow_data or 0
    
    def extract_pressure(pressure_data):
        """提取压力数据：可能是数值或 {'pressure': float} 结构"""
        if isinstance(pressure_data, dict):
            return pressure_data.get('pressure', 0)
        return pressure_data or 0
    
    # ========================================
    # 解析 DB1 弧流弧压数据 (来自 arc_data，已通过 converter_elec_db1 转换)
    # ========================================
    # 新结构 (使用 converter_elec_db1.py 转换后):
    # - arc_data['arc_current'] -> {'A': value_A, 'B': value_A, 'C': value_A} (单位: A)
    # - arc_data['arc_voltage'] -> {'A': value_V, 'B': value_V, 'C': value_V} (单位: V)
    # 弧流目标值: 5978 A (梯形图设定值 2989 × 2)
    # 弧压目标值: 70-90 V (靠近 80V)
    
    arc_current = arc_data.get('arc_current', {})
    arc_voltage = arc_data.get('arc_voltage', {})
    
    # 从转换后的数据获取弧流弧压 (单位: A 和 V)
    arc_currents_A = [
        arc_current.get('A', 0.0),  # A相弧流 (A)
        arc_current.get('B', 0.0),  # B相弧流 (A)
        arc_current.get('C', 0.0),  # C相弧流 (A)
    ]
    arc_voltages_v = [
        arc_voltage.get('A', 0.0),  # A相弧压 (V)
        arc_voltage.get('B', 0.0),  # B相弧压 (V)
        arc_voltage.get('C', 0.0),  # C相弧压 (V)
    ]
    
    # 解析 DB33 电表数据 (转换后的值) - 用于功率和能耗
    elec_converted = electricity_data.get('converted', {})
    
    # 功率和能耗 (仍从 DB33 获取，如果有的话)
    power_kw = elec_converted.get('Pt', 0.0)
    energy_kwh = elec_converted.get('ImpEp', 0.0)
    
    # 构建返回数据
    response_data = {
        # 电极数据 (深度 + 弧流 + 弧压) - 使用 DB1 弧流弧压数据
        "electrodes": [
            {
                "id": 1,
                "name": "电极1",
                "depth_mm": extract_depth(electrode_depths.get('LENTH1')),
                "current_A": arc_currents_A[0],    # A相弧流 (A) - 目标值约5978A
                "voltage_V": arc_voltages_v[0],    # A相弧压 (V)
            },
            {
                "id": 2,
                "name": "电极2", 
                "depth_mm": extract_depth(electrode_depths.get('LENTH2')),
                "current_A": arc_currents_A[1],    # B相弧流 (A)
                "voltage_V": arc_voltages_v[1],    # B相弧压 (V)
            },
            {
                "id": 3,
                "name": "电极3",
                "depth_mm": extract_depth(electrode_depths.get('LENTH3')),
                "current_A": arc_currents_A[2],    # C相弧流 (A)
                "voltage_V": arc_voltages_v[2],    # C相弧压 (V)
            },
        ],
        
        # 电表数据 (功率/能耗从 DB33, 弧流弧压从 DB1)
        "electricity": {
            "power_kW": power_kw,
            "energy_kWh": energy_kwh,
            "currents_A": arc_currents_A,  # 弧流 (A) - 直接使用转换后的值
            "voltages_V": arc_voltages_v,  # 弧压 (V)
            "timestamp": arc_result.get('timestamp'),  # 使用弧流弧压时间戳
        },
        
        # 冷却水数据 (炉皮 + 炉盖)
        # 根据用户反馈的PLC地址映射:
        # - 压力-过滤器进: 地址3 -> WATER_PRESS_1 (offset 12) -> 炉皮
        # - 压力-过滤器出: 地址4 -> WATER_PRESS_2 (offset 14) -> 炉盖
        # - 流量-炉皮: 地址12 -> WATER_FLOW_1 (offset 16)
        # - 流量-炉盖: 地址14 -> WATER_FLOW_2 (offset 18)
        # 注意: 原始单位是 MPa，需要 * 1000 转换为 kPa
        "cooling": {
            # 炉皮冷却水 (WATER_FLOW_1=流量, WATER_PRESS_1=过滤器进口压力)
            "furnace_shell": {
                "flow_m3h": extract_flow(cooling_flows.get('WATER_FLOW_1')),  # 流速 m³/h (地址12)
                "pressure_kPa": extract_pressure(cooling_pressures.get('WATER_PRESS_1')) * 1000,  # 过滤器进口压力 (kPa)
                "total_m3": modbus_data.get('furnace_shell_total_volume', 0.0),  # 累计流量 m³
            },
            # 炉盖冷却水 (WATER_FLOW_2=流量, WATER_PRESS_2=过滤器出口压力)
            "furnace_cover": {
                "flow_m3h": extract_flow(cooling_flows.get('WATER_FLOW_2')),  # 流速 m³/h (地址14)
                "pressure_kPa": extract_pressure(cooling_pressures.get('WATER_PRESS_2')) * 1000,  # 过滤器出口压力 (kPa)
                "total_m3": modbus_data.get('furnace_cover_total_volume', 0.0),  # 累计流量 m³
            },
            # 前置过滤器压差 = 炉皮水压 - 炉盖水压 (kPa)
            "filter_pressure_diff_kPa": (extract_pressure(cooling_pressures.get('WATER_PRESS_1')) - extract_pressure(cooling_pressures.get('WATER_PRESS_2'))) * 1000,
            "timestamp": modbus_result.get('timestamp'),
        },
        
        # 料仓数据 (包含投料总量)
        "hopper": {
            "weight_kg": weight_data.get('weight', 0),
            "feeding_total_kg": feeding_total_kg,  # 当前批次投料总量
            "success": weight_data.get('success', False),
            "timestamp": weight_result.get('timestamp'),
        },
        
        # 批次信息
        "batch": batch_result,
        
        # 数据时间戳汇总
        "timestamps": {
            "modbus": modbus_result.get('timestamp'),
            "electricity": electricity_result.get('timestamp'),
            "weight": weight_result.get('timestamp'),
        }
    }
    
    return {
        "success": True,
        "data": response_data,
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


# ============================================================
# 电表数据接口 (DB33)
# ============================================================
@router.get("/electricity")
async def get_electricity():
    """获取电表实时数据 (DB33, CT变比=20)
    
    返回:
    - raw: 原始值 (未乘变比)
    - converted: 转换后值 (已乘 CT/PT 变比)
    - summary: 核心 8 字段摘要
    """
    data = get_latest_electricity_data()
    return {
        "success": True,
        "data": data,
        "error": None
    }


# ============================================================
# 料仓重量接口 (Modbus RTU)
# ============================================================
@router.get("/hopper/weight")
async def get_hopper_weight():
    """获取料仓净重实时数据 (Modbus RTU)
    
    通信参数: COM1, 19200-8-E-1
    
    返回:
    - weight: 净重 (kg)
    - success: 读取是否成功
    - error: 错误信息 (如有)
    """
    data = get_latest_weight_data()
    return {
        "success": True,
        "data": data,
        "error": None
    }


# ============================================================
# 轮询统计接口
# ============================================================
@router.get("/polling/stats")
async def get_stats():
    """获取轮询服务统计信息
    
    返回:
    - running: 是否运行中
    - stats: 轮询计数/成功/失败统计
    - buffer_size: 当前缓存点数
    - *_data_age: 各数据源最后更新时间距今秒数
    """
    stats = get_polling_stats()
    return {
        "success": True,
        "data": stats,
        "error": None
    }

