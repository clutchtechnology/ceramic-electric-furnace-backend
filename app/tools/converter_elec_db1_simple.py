# ============================================================
# 文件说明: converter_elec_db1_simple.py - DB1 弧流弧压数据转换器（简化版）
# ============================================================
# 功能:
#   1. 直接使用 DB1 解析后的原始弧流弧压数据（不做校准计算）
#   2. UVW三相（对应ABC三相数据）
#   3. 12个数据点：U/V/W弧流(3) + U/V/W弧压(3) + U/V/W弧流设定值(3) + 手动死区百分比(1) + 灵敏度(2保留)
#   4. 单位：弧压V，弧流A，手动死区%
# ============================================================
# 【数据库写入说明 - DB1 弧流弧压数据】
# ============================================================
# Measurement: sensor_data
# Tags:
#   - device_type: electric_furnace
#   - module_type: arc_data
#   - device_id: electrode
#   - batch_code: 批次号 (动态)
# Fields (共10个数据点):
# ============================================================
# 基础字段 (每次轮询都写入):
#   - arc_current_U: U相弧流 (A)
#   - arc_current_V: V相弧流 (A)
#   - arc_current_W: W相弧流 (A)
#   - arc_voltage_U: U相弧压 (V)
#   - arc_voltage_V: V相弧压 (V)
#   - arc_voltage_W: W相弧压 (V)
# ============================================================
# 设定值字段 (仅在变化时写入):
#   - arc_current_setpoint_U: U相弧流设定值 (A)
#   - arc_current_setpoint_V: V相弧流设定值 (A)
#   - arc_current_setpoint_W: W相弧流设定值 (A)
#   - manual_deadzone_percent: 手动死区百分比 (%)
# ============================================================
# 写入逻辑:
#   - 轮询间隔: 5秒(默认) / 0.2秒(冶炼中)
#   - 批量写入: 20次轮询后写入 (4秒)
#   - 变化检测: 设定值和死区仅在变化时才写入，减少存储量
# ============================================================

from typing import Dict, Any
from dataclasses import dataclass
from datetime import datetime


# ============================================================
# 数据类定义
# ============================================================

@dataclass
class ArcPhaseDataSimple:
    """单相弧流弧压数据（简化版）"""
    phase: str  # 相位: U, V, W
    current_A: float = 0.0      # 弧流 (A)
    voltage_V: float = 0.0      # 弧压 (V)
    setpoint_A: float = 0.0     # 弧流设定值 (A)


@dataclass
class ArcDataSimple:
    """三相弧流弧压数据 + 设定值 + 手动死区（简化版）"""
    phase_U: ArcPhaseDataSimple
    phase_V: ArcPhaseDataSimple
    phase_W: ArcPhaseDataSimple
    manual_deadzone_percent: float = 0.0  # 手动死区百分比 (%)
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'phase_U': {
                'current_A': self.phase_U.current_A,
                'voltage_V': self.phase_U.voltage_V,
                'setpoint_A': self.phase_U.setpoint_A,
            },
            'phase_V': {
                'current_A': self.phase_V.current_A,
                'voltage_V': self.phase_V.voltage_V,
                'setpoint_A': self.phase_V.setpoint_A,
            },
            'phase_W': {
                'current_A': self.phase_W.current_A,
                'voltage_V': self.phase_W.voltage_V,
                'setpoint_A': self.phase_W.setpoint_A,
            },
            'manual_deadzone_percent': self.manual_deadzone_percent,
            'timestamp': self.timestamp,
        }
    
    def get_currents_A(self) -> tuple:
        """获取三相弧流值 (A)"""
        return (self.phase_U.current_A, self.phase_V.current_A, self.phase_W.current_A)
    
    def get_voltages_V(self) -> tuple:
        """获取三相弧压值 (V)"""
        return (self.phase_U.voltage_V, self.phase_V.voltage_V, self.phase_W.voltage_V)
    
    def get_setpoints_A(self) -> tuple:
        """获取三相弧流设定值 (A)"""
        return (self.phase_U.setpoint_A, self.phase_V.setpoint_A, self.phase_W.setpoint_A)


# ============================================================
# 1: 数据转换函数模块
# ============================================================

def convert_db1_arc_data_simple(parsed_data: Dict[str, Any]) -> ArcDataSimple:
    """从 DB1 解析结果中提取弧流弧压数据（直接使用原始值）
    
    Args:
        parsed_data: DB1 解析器返回的数据字典
        
    Returns:
        ArcDataSimple 对象
    """
    arc_current = parsed_data.get('arc_current', {})
    arc_voltage = parsed_data.get('arc_voltage', {})
    vw_variables = parsed_data.get('vw_variables', {})
    
    # U相: 弧流(offset 10), 弧压(offset 12), 设定值(offset 32)
    phase_U = ArcPhaseDataSimple(
        phase='U',
        current_A=float(arc_current.get('arc_current_U', 0)),
        voltage_V=float(arc_voltage.get('arc_voltage_U', 0)),
        setpoint_A=float(vw_variables.get('arc_current_setpoint_U', 0)),
    )
    
    # V相: 弧流(offset 16), 弧压(offset 18), 设定值(offset 36)
    phase_V = ArcPhaseDataSimple(
        phase='V',
        current_A=float(arc_current.get('arc_current_V', 0)),
        voltage_V=float(arc_voltage.get('arc_voltage_V', 0)),
        setpoint_A=float(vw_variables.get('arc_current_setpoint_V', 0)),
    )
    
    # W相: 弧流(offset 22), 弧压(offset 24), 设定值(offset 40)
    phase_W = ArcPhaseDataSimple(
        phase='W',
        current_A=float(arc_current.get('arc_current_W', 0)),
        voltage_V=float(arc_voltage.get('arc_voltage_W', 0)),
        setpoint_A=float(vw_variables.get('arc_current_setpoint_W', 0)),
    )
    
    # 手动死区百分比（offset 48）
    manual_deadzone_percent = float(vw_variables.get('manual_deadzone_percent', 0))
    
    return ArcDataSimple(
        phase_U=phase_U,
        phase_V=phase_V,
        phase_W=phase_W,
        manual_deadzone_percent=manual_deadzone_percent,
        timestamp=parsed_data.get('timestamp', datetime.now().isoformat()),
    )


def convert_to_api_format_simple(arc_data: ArcDataSimple) -> Dict[str, Any]:
    """转换为 API 返回格式
    
    Args:
        arc_data: ArcDataSimple 对象
        
    Returns:
        API 格式的字典
    """
    currents = arc_data.get_currents_A()
    voltages = arc_data.get_voltages_V()
    setpoints = arc_data.get_setpoints_A()
    
    return {
        'arc_current': {
            'U': currents[0],
            'V': currents[1],
            'W': currents[2],
            'unit': 'A',
        },
        'arc_voltage': {
            'U': voltages[0],
            'V': voltages[1],
            'W': voltages[2],
            'unit': 'V',
        },
        'setpoints': {
            'U': setpoints[0],
            'V': setpoints[1],
            'W': setpoints[2],
            'unit': 'A',
        },
        'manual_deadzone_percent': arc_data.manual_deadzone_percent,
        'timestamp': arc_data.timestamp,
    }


def convert_to_influx_fields_simple(arc_data: ArcDataSimple) -> Dict[str, float]:
    """转换为 InfluxDB 字段格式（10个数据点）
    
    Args:
        arc_data: ArcDataSimple 对象
        
    Returns:
        InfluxDB fields 字典（10个数据点）
    """
    return {
        # 弧流（3个）
        'arc_current_U': arc_data.phase_U.current_A,
        'arc_current_V': arc_data.phase_V.current_A,
        'arc_current_W': arc_data.phase_W.current_A,
        
        # 弧压（3个）
        'arc_voltage_U': arc_data.phase_U.voltage_V,
        'arc_voltage_V': arc_data.phase_V.voltage_V,
        'arc_voltage_W': arc_data.phase_W.voltage_V,
        
        # 弧流设定值（3个）
        'arc_current_setpoint_U': arc_data.phase_U.setpoint_A,
        'arc_current_setpoint_V': arc_data.phase_V.setpoint_A,
        'arc_current_setpoint_W': arc_data.phase_W.setpoint_A,
        
        # 手动死区百分比（1个）
        'manual_deadzone_percent': arc_data.manual_deadzone_percent,
    }


# ============================================================
# 2: 变化检测转换模块
# ============================================================
def convert_to_influx_fields_with_change_detection(
    arc_data: ArcDataSimple, 
    prev_setpoints: tuple = None, 
    prev_deadzone: float = None
) -> Dict[str, Any]:
    """转换为 InfluxDB 字段格式（带变化检测）
    
    设定值和死区仅在变化时才返回
    
    Args:
        arc_data: ArcDataSimple 对象
        prev_setpoints: 上一次的设定值 (U, V, W)
        prev_deadzone: 上一次的手动死区百分比
        
    Returns:
        包含 fields 和 has_setpoint_change 的字典
    """
    current_setpoints = arc_data.get_setpoints_A()
    current_deadzone = arc_data.manual_deadzone_percent
    
    # 基础字段（总是写入）
    fields = {
        'arc_current_U': arc_data.phase_U.current_A,
        'arc_current_V': arc_data.phase_V.current_A,
        'arc_current_W': arc_data.phase_W.current_A,
        'arc_voltage_U': arc_data.phase_U.voltage_V,
        'arc_voltage_V': arc_data.phase_V.voltage_V,
        'arc_voltage_W': arc_data.phase_W.voltage_V,
    }
    
    # 检测设定值变化
    setpoint_changed = False
    if prev_setpoints is None:
        setpoint_changed = True
    elif current_setpoints != prev_setpoints:
        setpoint_changed = True
    
    # 检测死区变化
    deadzone_changed = False
    if prev_deadzone is None:
        deadzone_changed = True
    elif abs(current_deadzone - prev_deadzone) > 0.01:  # 容差0.01%
        deadzone_changed = True
    
    # 仅在变化时添加设定值
    if setpoint_changed:
        fields['arc_current_setpoint_U'] = current_setpoints[0]
        fields['arc_current_setpoint_V'] = current_setpoints[1]
        fields['arc_current_setpoint_W'] = current_setpoints[2]
    
    # 仅在变化时添加死区
    if deadzone_changed:
        fields['manual_deadzone_percent'] = current_deadzone
    
    return {
        'fields': fields,
        'has_setpoint_change': setpoint_changed,
        'has_deadzone_change': deadzone_changed,
        'current_setpoints': current_setpoints,
        'current_deadzone': current_deadzone,
    }


# ============================================================
# 测试代码
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("弧流弧压转换器测试（简化版 - UVW三相 + 独立设定值）")
    print("=" * 60)
    
    # 模拟 DB1 解析数据
    mock_parsed = {
        'arc_current': {
            'arc_current_U_scale': 5978,   # U相弧流 (A)
            'arc_current_V_scale': 6000,   # V相弧流 (A)
            'arc_current_W_scale': 5950,   # W相弧流 (A)
        },
        'arc_voltage': {
            'arc_voltage_U_scale': 80,     # U相弧压 (V)
            'arc_voltage_V_scale': 75,     # V相弧压 (V)
            'arc_voltage_W_scale': 78,     # W相弧压 (V)
        },
        'vw_variables': {
            'arc_current_setpoint_U': 6000,  # U相弧流设定值 (A) - offset 32
            'arc_current_setpoint_V': 6000,  # V相弧流设定值 (A) - offset 36
            'arc_current_setpoint_W': 6000,  # W相弧流设定值 (A) - offset 40
            'manual_deadzone_percent': 5,    # 手动死区百分比 (%) - offset 48
        },
        'timestamp': datetime.now().isoformat(),
    }
    
    arc_data = convert_db1_arc_data_simple(mock_parsed)
    
    print(f"\n【原始数据（直接使用）】")
    print(f"   U相弧流: {arc_data.phase_U.current_A} A, 设定值: {arc_data.phase_U.setpoint_A} A")
    print(f"   U相弧压: {arc_data.phase_U.voltage_V} V")
    print(f"   V相弧流: {arc_data.phase_V.current_A} A, 设定值: {arc_data.phase_V.setpoint_A} A")
    print(f"   V相弧压: {arc_data.phase_V.voltage_V} V")
    print(f"   W相弧流: {arc_data.phase_W.current_A} A, 设定值: {arc_data.phase_W.setpoint_A} A")
    print(f"   W相弧压: {arc_data.phase_W.voltage_V} V")
    print(f"   手动死区百分比: {arc_data.manual_deadzone_percent}%")
    
    # API 格式
    print("\n【API 格式】")
    api_format = convert_to_api_format_simple(arc_data)
    print(f"   弧流: U={api_format['arc_current']['U']:.1f}, "
          f"V={api_format['arc_current']['V']:.1f}, "
          f"W={api_format['arc_current']['W']:.1f} A")
    print(f"   弧压: U={api_format['arc_voltage']['U']:.1f}, "
          f"V={api_format['arc_voltage']['V']:.1f}, "
          f"W={api_format['arc_voltage']['W']:.1f} V")
    print(f"   设定值: U={api_format['setpoints']['U']:.1f}, "
          f"V={api_format['setpoints']['V']:.1f}, "
          f"W={api_format['setpoints']['W']:.1f} A")
    print(f"   手动死区: {api_format['manual_deadzone_percent']}%")
    
    # InfluxDB 格式（10个数据点）
    print("\n【InfluxDB 字段（10个数据点）】")
    influx_fields = convert_to_influx_fields_simple(arc_data)
    for i, (k, v) in enumerate(influx_fields.items(), 1):
        print(f"   {i}. {k}: {v}")
    
    print("\n" + "=" * 60)
