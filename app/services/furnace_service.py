"""电炉后端 - 电炉数据服务"""

from typing import List, Dict, Any
from datetime import datetime, timezone

from app.services.polling_data_processor import (
    get_latest_modbus_data, 
    get_latest_status_data,
    get_latest_weight_data,
    get_latest_electricity_data,
)

# 设备清单（目前 DB32 只对应一台电炉，预留扩展位）
FURNACE_CONFIG = [
    {"device_id": "furnace_1", "name": "1号电炉", "zones": 3},
]


def get_furnace_list() -> List[Dict[str, Any]]:
    """获取电炉列表"""
    return FURNACE_CONFIG.copy()


def _build_realtime_payload(latest_modbus: Dict[str, Any], latest_status: Dict[str, Any]) -> Dict[str, Any]:
    """将缓存的 DB32/DB30 数据转换为前端友好的结构"""
    data = latest_modbus.get("data", {}) if latest_modbus else {}
    ts = latest_modbus.get("timestamp") if latest_modbus else None

    # 设备状态：有数据即视为 online，否则 offline
    status = "online" if data else "offline"

    # 红外测距（三根电极）
    electrode_depths = []
    for name, item in data.get("electrode_depths", {}).items():
        electrode_depths.append({
            "plc_variable": name,
            "distance_mm": item.get("distance", 0),
            "high": item.get("high", 0),
            "low": item.get("low", 0),
            "unit": item.get("unit", "mm"),
        })

    # 冷却水压力（两路）
    cooling_pressures = []
    for name, item in data.get("cooling_pressures", {}).items():
        cooling_pressures.append({
            "plc_variable": name,
            "pressure_mpa": item.get("pressure", 0),
            "raw": item.get("raw", 0),
            "unit": item.get("unit", "MPa"),
        })

    # 冷却水流量（两路）
    cooling_flows = []
    for name, item in data.get("cooling_flows", {}).items():
        cooling_flows.append({
            "plc_variable": name,
            "flow_m3h": item.get("flow", 0),
            "raw": item.get("raw", 0),
            "unit": item.get("unit", "m³/h"),
        })

    # 蝶阀状态监测（Byte类型，每bit对应一个蝶阀的开关状态）
    valve_status = data.get("valve_status", {})
    valve_controls = []
    if valve_status:
        valve_controls = [
            {
                "valve_id": i,
                "name": f"蝶阀{i}",
                "is_open": bool(valve_status.get(f"valve_{i}", False)),
                "status": "开启" if valve_status.get(f"valve_{i}", False) else "关闭",
            }
            for i in range(1, 9)  # 蝶阀1-8
        ]
        # 添加汇总信息
        valve_summary = {
            "status_byte": valve_status.get("status_byte", 0),
            "status_hex": valve_status.get("status_hex", "16#00"),
            "open_count": valve_status.get("open_count", 0),
            "total_count": 8,
        }
    else:
        valve_summary = None

    # 通信状态摘要（DB30）
    status_summary = None
    if latest_status and latest_status.get("data"):
        summary = latest_status["data"].get("summary", {})
        status_summary = {
            "total": summary.get("total", 0),
            "healthy": summary.get("healthy", 0),
            "error": summary.get("error", 0),
            "timestamp": latest_status.get("timestamp"),
        }

    return {
        "status": status,
        "electrode_depths": electrode_depths,
        "cooling_pressures": cooling_pressures,
        "cooling_flows": cooling_flows,
        "valve_controls": valve_controls,
        "valve_summary": valve_summary,  # 蝶阀状态汇总
        "status_summary": status_summary,
        "updated_at": ts,
    }


def get_realtime_data() -> List[Dict[str, Any]]:
    """获取所有电炉实时数据（从轮询缓存转换）
    
    数据来源:
    - DB32: 传感器数据 (红外测距/压力/流量/蝶阀)
    - DB30: 通信状态
    - DB33: 电表数据
    - Modbus RTU: 料仓净重
    """
    latest_modbus = get_latest_modbus_data()
    latest_status = get_latest_status_data()
    latest_elec = get_latest_electricity_data()
    latest_weight = get_latest_weight_data()

    payload = _build_realtime_payload(latest_modbus, latest_status)
    
    # 添加电表数据
    elec_data = latest_elec.get("data", {}) if latest_elec else {}
    converted = elec_data.get("converted", {})
    summary = elec_data.get("summary", {})
    
    electricity = {
        "Pt": converted.get("Pt", 0.0),        # 总功率 kW
        "Ua_0": converted.get("Ua_0", 0.0),    # A相电压 V
        "I_0": converted.get("I_0", 0.0),      # A相电流 A
        "I_1": converted.get("I_1", 0.0),      # B相电流 A
        "I_2": converted.get("I_2", 0.0),      # C相电流 A
        "ImpEp": converted.get("ImpEp", 0.0),  # 累计电能 kWh
        "ct_ratio": elec_data.get("ct_ratio", 20),
        "updated_at": latest_elec.get("timestamp") if latest_elec else None,
    }
    
    # 添加料仓重量数据
    weight_data = latest_weight.get("data", {}) if latest_weight else {}
    hopper = {
        "net_weight": weight_data.get("weight", 0),  # 净重 kg
        "unit": weight_data.get("unit", "kg"),
        "success": weight_data.get("success", False),
        "error": weight_data.get("error"),
        "updated_at": latest_weight.get("timestamp") if latest_weight else None,
    }

    result = []
    for furnace in FURNACE_CONFIG:
        result.append({
            "device_id": furnace["device_id"],
            "name": furnace["name"],
            "zones": furnace["zones"],
            **payload,
            "electricity": electricity,
            "hopper": hopper,
        })

    return result
