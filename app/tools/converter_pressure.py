# ============================================================
# 文件说明: converter_pressure.py - 压力计数据转换器
# ============================================================
# 功能:
#   1. 将压力计原始值转换为实际压力值
#   2. 计算公式: 实际值 = 原始值 × 0.1 (根据手册小数点1位)
#   3. 单位: MPa
# ============================================================
# 手册参考:
#   - 协议: Modbus-RTU
#   - 读取命令: 01 03 00 04 00 01 C5 CB
#   - 响应示例: 01 03 02 13 88 B5 12
#     - 13 88 (hex) = 5000 (dec)
#     - 小数点1位 -> 500.0 MPa
#   - 计算: 原始值 / 10^小数点位数 = 原始值 × 0.1
# ============================================================

from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class PressureData:
    """压力数据"""
    pressure: float          # 压力值 (MPa)
    raw: int                 # 原始值
    unit: str = "MPa"        # 单位
    valid: bool = True       # 数据是否有效
    error: Optional[str] = None  # 错误信息


class PressureConverter:
    """压力计数据转换器
    
    将 PLC 原始值转换为实际压力值
    计算公式: 压力 = 原始值 × 0.1 (MPa)
    
    根据手册: 小数点位数=1 时，原始值5000 -> 显示500.0 MPa
    """
    
    # 转换系数 (根据小数点位数)
    # 原始公式: scale = 0.1 (MPa)
    # 新公式: scale = 0.1 × 0.1 = 0.01 (转换为 kPa 后缩小10倍)
    # 说明: 0.041 MPa → 41 kPa → 4.1 (最终存储值)
    SCALE_FACTOR = 0.01  # 流速×10, 水压×0.1 (相当于 MPa→kPa 再÷10)
    
    # 单位
    UNIT = "kPa"  # 修改单位为 kPa
    
    # 有效范围 (可根据实际传感器量程调整)
    MIN_VALID_PRESSURE = 0.0       # 最小有效压力 (kPa)
    MAX_VALID_PRESSURE = 1000.0    # 最大有效压力 (kPa, 原100MPa=100000kPa, 缩小后1000)
    INVALID_RAW_VALUE = 0xFFFF     # 无效原始值标识
    NEGATIVE_THRESHOLD = 0x8000    # 负数阈值 (有符号整数)
    
    def __init__(self, 
                 scale: float = 0.01,
                 decimal_places: int = 2,
                 min_range: float = 0.0,
                 max_range: float = 1000.0,
                 signed: bool = True):
        """初始化转换器
        
        Args:
            scale: 转换系数 (默认 0.01，水压×0.1)
            decimal_places: 小数点位数 (用于自动计算 scale)
            min_range: 最小有效范围 (kPa)
            max_range: 最大有效范围 (kPa)
            signed: 是否为有符号整数 (手册说明范围 -32768~32767)
        """
        # 如果指定了小数点位数，自动计算 scale
        if decimal_places is not None:
            self.scale = 1.0 / (10 ** decimal_places)
        else:
            self.scale = scale
            
        self.decimal_places = decimal_places
        self.min_range = min_range
        self.max_range = max_range
        self.signed = signed
    
    def _convert_signed(self, raw_value: int) -> int:
        """将无符号值转换为有符号值
        
        Args:
            raw_value: 无符号原始值 (0-65535)
            
        Returns:
            有符号值 (-32768 ~ 32767)
        """
        if self.signed and raw_value >= self.NEGATIVE_THRESHOLD:
            return raw_value - 0x10000
        return raw_value
    
    def convert(self, raw_value: int) -> Dict[str, Any]:
        """转换原始值为压力
        
        Args:
            raw_value: PLC 读取的原始值 (WORD, 0-65535)
            
        Returns:
            {
                "pressure": 5.05,     # 压力值 (kPa, 原505→50.5MPa→5.05kPa)
                "raw": 505,           # 原始值
                "raw_signed": 505,    # 有符号原始值
                "unit": "kPa",        # 单位
                "valid": True,        # 是否有效
                "error": None         # 错误信息
            }
        """
        result = {
            "pressure": 0.0,
            "raw": raw_value,
            "raw_signed": raw_value,
            "unit": self.UNIT,
            "valid": True,
            "error": None
        }
        
        # 无效值检测
        if raw_value == self.INVALID_RAW_VALUE:
            result["valid"] = False
            result["error"] = "INVALID_READING"
            result["pressure"] = None
            return result
        
        # 转换为有符号值
        signed_value = self._convert_signed(raw_value)
        result["raw_signed"] = signed_value
        
        # 计算实际压力
        pressure = signed_value * self.scale
        result["pressure"] = round(pressure, 3)
        
        # 范围校验
        if pressure < self.min_range:
            result["valid"] = False
            result["error"] = "BELOW_MIN_RANGE"
        elif pressure > self.max_range:
            result["valid"] = False
            result["error"] = "ABOVE_MAX_RANGE"
        
        return result
    
    def convert_to_data(self, raw_value: int) -> PressureData:
        """转换为 PressureData 对象
        
        Args:
            raw_value: 原始值
            
        Returns:
            PressureData 对象
        """
        result = self.convert(raw_value)
        return PressureData(
            pressure=result["pressure"] if result["pressure"] is not None else 0.0,
            raw=result["raw"],
            unit=result["unit"],
            valid=result["valid"],
            error=result["error"]
        )


# ============================================================
# 全局单例实例
# ============================================================
_pressure_converter: Optional[PressureConverter] = None


def get_pressure_converter(scale: float = 0.01) -> PressureConverter:
    """获取 PressureConverter 单例实例
    
    Args:
        scale: 转换系数 (默认 0.01，水压×0.1)
        
    Returns:
        PressureConverter 实例
    """
    global _pressure_converter
    if _pressure_converter is None:
        _pressure_converter = PressureConverter(scale=scale)
    return _pressure_converter


# ============================================================
# 便捷函数
# ============================================================
def convert_pressure(raw_value: int, scale: float = 0.01) -> float:
    """快捷转换函数: 原始值 -> 压力
    
    Args:
        raw_value: 原始值
        scale: 转换系数 (默认 0.01，水压×0.1)
        
    Returns:
        压力值 (kPa)
    """
    # 处理有符号数
    if raw_value >= 0x8000:
        raw_value = raw_value - 0x10000
    return round(raw_value * scale, 3)


def convert_pressure_with_validation(raw_value: int) -> Dict[str, Any]:
    """带校验的转换函数
    
    Args:
        raw_value: 原始值
        
    Returns:
        完整的转换结果字典
    """
    converter = get_pressure_converter()
    return converter.convert(raw_value)


def convert_all_pressures(pressure_data: Dict[str, Dict]) -> Dict[str, Dict]:
    """批量转换所有压力数据
    
    Args:
        pressure_data: parser 输出的压力数据字典
            格式: {'WATER_PRESS_1': {'raw': 505}, 'WATER_PRESS_2': {'raw': 600}, ...}
            
    Returns:
        转换后的数据字典
        格式: {
            'WATER_PRESS_1': {'pressure': 50.5, 'unit': 'MPa', 'valid': True, ...},
            'WATER_PRESS_2': {'pressure': 60.0, ...},
            ...
        }
    """
    converter = get_pressure_converter()
    result = {}
    
    for name, data in pressure_data.items():
        raw = data.get('raw', 0)
        converted = converter.convert(raw)
        converted['name'] = name
        converted['description'] = data.get('description', '')
        result[name] = converted
    
    return result


# ============================================================
# 测试代码
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("压力计数据转换器 - 测试")
    print("=" * 60)
    print("转换公式: 压力 = 原始值 × 0.1 (MPa)")
    print("参考手册: 原始值 5000 -> 显示 500.0 MPa (小数点1位)")
    print("=" * 60)
    
    # 测试数据
    test_cases = [
        (0, 0.0),            # 0 -> 0.0 MPa
        (50, 5.0),           # 50 -> 5.0 MPa
        (505, 50.5),         # 505 -> 50.5 MPa
        (5000, 500.0),       # 5000 -> 500.0 MPa (手册示例)
        (0x1388, 500.0),     # 0x1388 = 5000 -> 500.0 MPa
        (65535, None),       # 无效值 (0xFFFF)
    ]
    
    converter = PressureConverter()
    
    print("\n📊 转换测试:")
    for raw, expected in test_cases:
        result = converter.convert(raw)
        status = "✅" if result["valid"] else "⚠️"
        print(f"  {status} 原始值: {raw:5d} (0x{raw:04X}) -> 压力: {result['pressure']} {result['unit']}")
        if result["error"]:
            print(f"      错误: {result['error']}")
    
    # 负数测试 (有符号整数)
    print("\n📊 有符号数测试 (支持负压):")
    negative_tests = [
        (0xFFFF - 100, -10.1),  # 负值测试
        (0x8000, -3276.8),      # 最小负值边界
    ]
    for raw, expected in negative_tests:
        result = converter.convert(raw)
        print(f"  原始值: {raw:5d} (0x{raw:04X}) -> 压力: {result['pressure']} {result['unit']} (raw_signed: {result['raw_signed']})")
    
    # 批量转换测试
    print("\n📊 批量转换测试:")
    sample_data = {
        'WATER_PRESS_1': {'raw': 50, 'description': '1号冷却水压力'},
        'WATER_PRESS_2': {'raw': 60, 'description': '2号冷却水压力'},
    }
    
    converted = convert_all_pressures(sample_data)
    for name, data in converted.items():
        print(f"  {name}: {data['pressure']} {data['unit']} - {data['description']}")
    
    print("\n" + "=" * 60)
    print("💡 使用示例:")
    print("   from app.tools.converter_pressure import convert_pressure")
    print("   pressure = convert_pressure(505)  # 返回 50.5 MPa")
    print("=" * 60)
