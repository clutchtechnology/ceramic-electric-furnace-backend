# ============================================================
# 文件说明: converter_elec_db1.py - DB1 弧流弧压数据转换器
# ============================================================
# 功能:
#   1. 将 DB1 解析后的原始弧流弧压数据转换为物理量
#   2. 提供弧流弧压的校准和修正逻辑
#   3. 弧流目标值: 约 5978 A (单位: A)
#   4. 弧压目标值: 约 70-90 V (靠近 80V)
# ============================================================
# 数据源:
#   - arc_current_X_scale: X相弧流比例放大值 (INT)
#   - arc_voltage_X_scale: X相弧压比例放大值 (INT)
#   - arc_current_X_normalized: X相弧流归一化值 (REAL, 备用)
#   - arc_voltage_X_normalized: X相弧压归一化值 (REAL, 备用)
# ============================================================

from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime


# ============================================================
# 常量定义
# ============================================================

# 弧流目标值 (A) - 梯形图设定值 2989 × 2 = 5978 A
ARC_CURRENT_TARGET_A = 5978

# 弧流有效范围 (直接使用原值) - 目标值 ±10%
ARC_CURRENT_VALID_MIN = 5380  # 5978 * 0.9
ARC_CURRENT_VALID_MAX = 6576  # 5978 * 1.1

# 弧流需要校准的阈值
ARC_CURRENT_CALIBRATION_THRESHOLD = 1000  # 需要校准的最小值

# 弧压目标值 (V)
ARC_VOLTAGE_TARGET_V = 80

# 弧压有效范围 (直接使用原值)
ARC_VOLTAGE_VALID_MIN = 70   # 最小有效值 (V)
ARC_VOLTAGE_VALID_MAX = 90   # 最大有效值 (V)

# 弧压需要校准的范围
ARC_VOLTAGE_CALIBRATION_MIN = 10   # 需要校准的最小值
ARC_VOLTAGE_CALIBRATION_MAX = 100  # 需要校准的最大值


# ============================================================
# 数据类定义
# ============================================================

@dataclass
class ArcPhaseData:
    """单相弧流弧压数据"""
    phase: str  # 相位: A, B, C
    current_raw: int = 0        # 弧流原始值 (scale)
    current_A: float = 0.0      # 弧流转换值 (A)
    voltage_raw: int = 0        # 弧压原始值 (scale)
    voltage_V: float = 0.0      # 弧压转换值 (V)
    current_calibrated: bool = False  # 弧流是否经过校准
    voltage_calibrated: bool = False  # 弧压是否经过校准
    current_multiplier: int = 1       # 弧流校准倍数
    voltage_multiplier: int = 1       # 弧压校准倍数


@dataclass
class ArcData:
    """三相弧流弧压数据"""
    phase_A: ArcPhaseData = None
    phase_B: ArcPhaseData = None
    phase_C: ArcPhaseData = None
    timestamp: str = ""
    
    def __post_init__(self):
        if self.phase_A is None:
            self.phase_A = ArcPhaseData(phase='A')
        if self.phase_B is None:
            self.phase_B = ArcPhaseData(phase='B')
        if self.phase_C is None:
            self.phase_C = ArcPhaseData(phase='C')
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'phase_A': {
                'current_raw': self.phase_A.current_raw,
                'current_A': self.phase_A.current_A,
                'voltage_raw': self.phase_A.voltage_raw,
                'voltage_V': self.phase_A.voltage_V,
                'current_calibrated': self.phase_A.current_calibrated,
                'voltage_calibrated': self.phase_A.voltage_calibrated,
            },
            'phase_B': {
                'current_raw': self.phase_B.current_raw,
                'current_A': self.phase_B.current_A,
                'voltage_raw': self.phase_B.voltage_raw,
                'voltage_V': self.phase_B.voltage_V,
                'current_calibrated': self.phase_B.current_calibrated,
                'voltage_calibrated': self.phase_B.voltage_calibrated,
            },
            'phase_C': {
                'current_raw': self.phase_C.current_raw,
                'current_A': self.phase_C.current_A,
                'voltage_raw': self.phase_C.voltage_raw,
                'voltage_V': self.phase_C.voltage_V,
                'current_calibrated': self.phase_C.current_calibrated,
                'voltage_calibrated': self.phase_C.voltage_calibrated,
            },
            'timestamp': self.timestamp,
        }
    
    def get_currents_A(self) -> Tuple[float, float, float]:
        """获取三相弧流 (A)"""
        return (self.phase_A.current_A, self.phase_B.current_A, self.phase_C.current_A)
    
    def get_voltages_V(self) -> Tuple[float, float, float]:
        """获取三相弧压 (V)"""
        return (self.phase_A.voltage_V, self.phase_B.voltage_V, self.phase_C.voltage_V)


# ============================================================
# 转换函数
# ============================================================

def convert_arc_current(raw_scale: int) -> Tuple[float, bool, int]:
    """转换弧流数据
    
    转换规则:
    1. 如果 5000 < raw_scale < 6500 (在目标值5978附近±10%)，直接使用原值 (单位: A)
    2. 如果 raw_scale > 1000，计算校准倍数:
       multiplier = 5978 // raw_scale (取整)
       result = raw_scale * multiplier
    3. 否则返回原值
    
    Args:
        raw_scale: 弧流比例放大原始值 (INT, 单位: A)
        
    Returns:
        (转换后的弧流值 A, 是否校准, 校准倍数)
    """
    if raw_scale <= 0:
        return 0.0, False, 1
    
    # 情况1: 在有效范围内 (目标值5978 ±10%)，直接使用
    if ARC_CURRENT_VALID_MIN < raw_scale < ARC_CURRENT_VALID_MAX:
        return float(raw_scale), False, 1
    
    # 情况2: 需要校准 (raw_scale > 1000 但不在有效范围)
    if raw_scale > ARC_CURRENT_CALIBRATION_THRESHOLD:
        multiplier = ARC_CURRENT_TARGET_A // raw_scale
        if multiplier < 1:
            multiplier = 1
        calibrated_value = raw_scale * multiplier
        return float(calibrated_value), True, multiplier
    
    # 情况3: 值太小，直接返回原值
    return float(raw_scale), False, 1


def convert_arc_voltage(raw_scale: int) -> Tuple[float, bool, int]:
    """转换弧压数据
    
    转换规则:
    1. 如果 70 < raw_scale < 90，直接使用原值 (单位: V)
    2. 如果 10 < raw_scale < 100 且 raw_scale < 80:
       multiplier = 80 // raw_scale (取整)
       result = raw_scale * multiplier
    3. 否则返回原值
    
    Args:
        raw_scale: 弧压比例放大原始值 (INT)
        
    Returns:
        (转换后的弧压值 V, 是否校准, 校准倍数)
    """
    if raw_scale <= 0:
        return 0.0, False, 1
    
    # 情况1: 在有效范围内，直接使用
    if ARC_VOLTAGE_VALID_MIN < raw_scale < ARC_VOLTAGE_VALID_MAX:
        return float(raw_scale), False, 1
    
    # 情况2: 需要校准 (10 < raw_scale < 100 且 raw_scale < 80)
    if ARC_VOLTAGE_CALIBRATION_MIN < raw_scale < ARC_VOLTAGE_CALIBRATION_MAX:
        if raw_scale < ARC_VOLTAGE_TARGET_V:
            multiplier = ARC_VOLTAGE_TARGET_V // raw_scale
            if multiplier < 1:
                multiplier = 1
            calibrated_value = raw_scale * multiplier
            return float(calibrated_value), True, multiplier
        else:
            # raw_scale >= 80, 直接使用
            return float(raw_scale), False, 1
    
    # 情况3: 其他情况，直接返回原值
    return float(raw_scale), False, 1


def convert_arc_phase(
    phase: str,
    current_scale: int,
    voltage_scale: int,
    current_normalized: float = 0.0,
    voltage_normalized: float = 0.0
) -> ArcPhaseData:
    """转换单相弧流弧压数据
    
    Args:
        phase: 相位 (A, B, C)
        current_scale: 弧流比例放大值 (INT)
        voltage_scale: 弧压比例放大值 (INT)
        current_normalized: 弧流归一化值 (REAL, 备用)
        voltage_normalized: 弧压归一化值 (REAL, 备用)
        
    Returns:
        ArcPhaseData 对象
    """
    # 转换弧流
    current_A, current_calibrated, current_multiplier = convert_arc_current(current_scale)
    
    # 转换弧压
    voltage_V, voltage_calibrated, voltage_multiplier = convert_arc_voltage(voltage_scale)
    
    return ArcPhaseData(
        phase=phase,
        current_raw=current_scale,
        current_A=current_A,
        voltage_raw=voltage_scale,
        voltage_V=voltage_V,
        current_calibrated=current_calibrated,
        voltage_calibrated=voltage_calibrated,
        current_multiplier=current_multiplier,
        voltage_multiplier=voltage_multiplier,
    )


def convert_db1_arc_data(parsed_data: Dict[str, Any]) -> ArcData:
    """从 DB1 解析结果中提取并转换弧流弧压数据
    
    Args:
        parsed_data: DB1 解析器返回的数据字典
        
    Returns:
        ArcData 对象
    """
    arc_current = parsed_data.get('arc_current', {})
    arc_voltage = parsed_data.get('arc_voltage', {})
    
    # A相
    phase_A = convert_arc_phase(
        phase='A',
        current_scale=arc_current.get('arc_current_A_scale', 0),
        voltage_scale=arc_voltage.get('arc_voltage_A_scale', 0),
        current_normalized=arc_current.get('arc_current_A_normalized', 0.0),
        voltage_normalized=arc_voltage.get('arc_voltage_A_normalized', 0.0),
    )
    
    # B相
    phase_B = convert_arc_phase(
        phase='B',
        current_scale=arc_current.get('arc_current_B_scale', 0),
        voltage_scale=arc_voltage.get('arc_voltage_B_scale', 0),
        current_normalized=arc_current.get('arc_current_B_normalized', 0.0),
        voltage_normalized=arc_voltage.get('arc_voltage_B_normalized', 0.0),
    )
    
    # C相
    phase_C = convert_arc_phase(
        phase='C',
        current_scale=arc_current.get('arc_current_C_scale', 0),
        voltage_scale=arc_voltage.get('arc_voltage_C_scale', 0),
        current_normalized=arc_current.get('arc_current_C_normalized', 0.0),
        voltage_normalized=arc_voltage.get('arc_voltage_C_normalized', 0.0),
    )
    
    return ArcData(
        phase_A=phase_A,
        phase_B=phase_B,
        phase_C=phase_C,
        timestamp=parsed_data.get('timestamp', datetime.now().isoformat()),
    )


def convert_to_api_format(arc_data: ArcData) -> Dict[str, Any]:
    """转换为 API 返回格式
    
    Args:
        arc_data: ArcData 对象
        
    Returns:
        API 格式的字典
    """
    currents = arc_data.get_currents_A()
    voltages = arc_data.get_voltages_V()
    
    return {
        'arc_current': {
            'A': currents[0],
            'B': currents[1],
            'C': currents[2],
            'unit': 'A',
        },
        'arc_voltage': {
            'A': voltages[0],
            'B': voltages[1],
            'C': voltages[2],
            'unit': 'V',
        },
        'calibration_info': {
            'A': {
                'current_calibrated': arc_data.phase_A.current_calibrated,
                'current_multiplier': arc_data.phase_A.current_multiplier,
                'voltage_calibrated': arc_data.phase_A.voltage_calibrated,
                'voltage_multiplier': arc_data.phase_A.voltage_multiplier,
            },
            'B': {
                'current_calibrated': arc_data.phase_B.current_calibrated,
                'current_multiplier': arc_data.phase_B.current_multiplier,
                'voltage_calibrated': arc_data.phase_B.voltage_calibrated,
                'voltage_multiplier': arc_data.phase_B.voltage_multiplier,
            },
            'C': {
                'current_calibrated': arc_data.phase_C.current_calibrated,
                'current_multiplier': arc_data.phase_C.current_multiplier,
                'voltage_calibrated': arc_data.phase_C.voltage_calibrated,
                'voltage_multiplier': arc_data.phase_C.voltage_multiplier,
            },
        },
        'timestamp': arc_data.timestamp,
    }


def convert_to_influx_fields(arc_data: ArcData) -> Dict[str, float]:
    """转换为 InfluxDB 字段格式
    
    Args:
        arc_data: ArcData 对象
        
    Returns:
        InfluxDB fields 字典
    """
    return {
        'arc_current_A': arc_data.phase_A.current_A,
        'arc_current_B': arc_data.phase_B.current_A,
        'arc_current_C': arc_data.phase_C.current_A,
        'arc_voltage_A': arc_data.phase_A.voltage_V,
        'arc_voltage_B': arc_data.phase_B.voltage_V,
        'arc_voltage_C': arc_data.phase_C.voltage_V,
        # 原始值 (用于调试)
        'arc_current_A_raw': float(arc_data.phase_A.current_raw),
        'arc_current_B_raw': float(arc_data.phase_B.current_raw),
        'arc_current_C_raw': float(arc_data.phase_C.current_raw),
        'arc_voltage_A_raw': float(arc_data.phase_A.voltage_raw),
        'arc_voltage_B_raw': float(arc_data.phase_B.voltage_raw),
        'arc_voltage_C_raw': float(arc_data.phase_C.voltage_raw),
    }


# ============================================================
# 单例转换器
# ============================================================

class ArcDataConverter:
    """弧流弧压数据转换器 (单例)"""
    
    _instance: Optional['ArcDataConverter'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # 配置参数 (可通过 configure 方法修改)
        self.current_target = ARC_CURRENT_TARGET_A
        self.current_valid_range = (ARC_CURRENT_VALID_MIN, ARC_CURRENT_VALID_MAX)
        self.current_calibration_threshold = ARC_CURRENT_CALIBRATION_THRESHOLD
        
        self.voltage_target = ARC_VOLTAGE_TARGET_V
        self.voltage_valid_range = (ARC_VOLTAGE_VALID_MIN, ARC_VOLTAGE_VALID_MAX)
        self.voltage_calibration_range = (ARC_VOLTAGE_CALIBRATION_MIN, ARC_VOLTAGE_CALIBRATION_MAX)
        
        self._initialized = True
        print("✅ 弧流弧压转换器初始化完成")
        print(f"   弧流目标: {self.current_target} A")
        print(f"   弧压目标: {self.voltage_target} V")
    
    def configure(
        self,
        current_target: int = None,
        voltage_target: int = None,
        current_valid_range: Tuple[int, int] = None,
        voltage_valid_range: Tuple[int, int] = None,
    ):
        """配置转换器参数
        
        Args:
            current_target: 弧流目标值 (A)
            voltage_target: 弧压目标值 (V)
            current_valid_range: 弧流有效范围 (min, max)
            voltage_valid_range: 弧压有效范围 (min, max)
        """
        if current_target is not None:
            self.current_target = current_target
        if voltage_target is not None:
            self.voltage_target = voltage_target
        if current_valid_range is not None:
            self.current_valid_range = current_valid_range
        if voltage_valid_range is not None:
            self.voltage_valid_range = voltage_valid_range
        
        print(f"⚙️ 弧流弧压转换器配置更新:")
        print(f"   弧流目标: {self.current_target} A")
        print(f"   弧压目标: {self.voltage_target} V")
    
    def convert(self, parsed_data: Dict[str, Any]) -> ArcData:
        """转换 DB1 解析数据"""
        return convert_db1_arc_data(parsed_data)
    
    def to_api_format(self, arc_data: ArcData) -> Dict[str, Any]:
        """转换为 API 格式"""
        return convert_to_api_format(arc_data)
    
    def to_influx_fields(self, arc_data: ArcData) -> Dict[str, float]:
        """转换为 InfluxDB 字段"""
        return convert_to_influx_fields(arc_data)


def get_arc_converter() -> ArcDataConverter:
    """获取弧流弧压转换器单例"""
    return ArcDataConverter()


# ============================================================
# 测试代码
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("弧流弧压转换器测试")
    print("=" * 60)
    
    # 测试弧流转换
    print("\n【弧流转换测试】")
    test_currents = [0, 500, 1500, 2989, 3000, 5100, 5300, 6000, 10000]
    for raw in test_currents:
        result, calibrated, multiplier = convert_arc_current(raw)
        status = f"(校准: ×{multiplier})" if calibrated else "(直接使用)"
        print(f"   原始值: {raw:6d} -> 转换后: {result:8.1f} A {status}")
    
    # 测试弧压转换
    print("\n【弧压转换测试】")
    test_voltages = [0, 15, 20, 40, 60, 75, 85, 95, 150]
    for raw in test_voltages:
        result, calibrated, multiplier = convert_arc_voltage(raw)
        status = f"(校准: ×{multiplier})" if calibrated else "(直接使用)"
        print(f"   原始值: {raw:4d} -> 转换后: {result:6.1f} V {status}")
    
    # 模拟 DB1 解析数据
    print("\n【完整转换测试】")
    mock_parsed = {
        'arc_current': {
            'arc_current_A_scale': 2989,
            'arc_current_B_scale': 3000,
            'arc_current_C_scale': 2950,
            'arc_current_A_normalized': 0.5,
            'arc_current_B_normalized': 0.5,
            'arc_current_C_normalized': 0.5,
        },
        'arc_voltage': {
            'arc_voltage_A_scale': 40,
            'arc_voltage_B_scale': 75,
            'arc_voltage_C_scale': 85,
            'arc_voltage_A_normalized': 0.5,
            'arc_voltage_B_normalized': 0.5,
            'arc_voltage_C_normalized': 0.5,
        },
        'timestamp': datetime.now().isoformat(),
    }
    
    arc_data = convert_db1_arc_data(mock_parsed)
    
    print(f"\n   A相弧流: {arc_data.phase_A.current_raw} -> {arc_data.phase_A.current_A} A")
    print(f"   A相弧压: {arc_data.phase_A.voltage_raw} -> {arc_data.phase_A.voltage_V} V")
    print(f"   B相弧流: {arc_data.phase_B.current_raw} -> {arc_data.phase_B.current_A} A")
    print(f"   B相弧压: {arc_data.phase_B.voltage_raw} -> {arc_data.phase_B.voltage_V} V")
    print(f"   C相弧流: {arc_data.phase_C.current_raw} -> {arc_data.phase_C.current_A} A")
    print(f"   C相弧压: {arc_data.phase_C.voltage_raw} -> {arc_data.phase_C.voltage_V} V")
    
    # API 格式
    print("\n【API 格式】")
    api_format = convert_to_api_format(arc_data)
    print(f"   弧流: A={api_format['arc_current']['A']:.1f}, "
          f"B={api_format['arc_current']['B']:.1f}, "
          f"C={api_format['arc_current']['C']:.1f} A")
    print(f"   弧压: A={api_format['arc_voltage']['A']:.1f}, "
          f"B={api_format['arc_voltage']['B']:.1f}, "
          f"C={api_format['arc_voltage']['C']:.1f} V")
    
    # InfluxDB 格式
    print("\n【InfluxDB 字段】")
    influx_fields = convert_to_influx_fields(arc_data)
    for k, v in influx_fields.items():
        print(f"   {k}: {v}")
    
    print("\n" + "=" * 60)
    print("✅ 弧流弧压转换器测试完成")
    print("=" * 60)
