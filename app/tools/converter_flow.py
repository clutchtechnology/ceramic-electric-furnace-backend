# ============================================================
# 文件说明: converter_flow.py - 流量计数据转换器
# ============================================================
# 功能:
#   1. 将流量计原始值转换为实际流量值
#   2. 计算公式: 实际值 = 原始值 * 0.1
#   3. 单位: m³/h (立方米/小时)
# ============================================================

from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class FlowData:
    """流量数据"""
    flow: float              # 流量值 (m³/h)
    raw: int                 # 原始值
    unit: str = "m³/h"       # 单位
    valid: bool = True       # 数据是否有效
    error: Optional[str] = None  # 错误信息


class FlowConverter:
    """流量计数据转换器
    
    将 PLC 原始值转换为实际流量值
    计算公式: 流量 = 原始值 * 0.1 (m³/h)
    """
    
    # 转换系数
    # 原始公式: scale = 0.1
    # 新公式: scale = 1.0 (流速×10)
    SCALE_FACTOR = 1.0
    
    # 单位
    UNIT = "m³/h"
    
    # 有效范围 (可根据实际传感器量程调整)
    MIN_VALID_FLOW = 0.0      # 最小有效流量
    MAX_VALID_FLOW = 10000.0  # 最大有效流量 (m³/h, 原1000×10=10000)
    INVALID_RAW_VALUE = 0xFFFF  # 无效原始值标识
    
    def __init__(self, 
                 scale: float = 1.0,
                 min_range: float = 0.0,
                 max_range: float = 10000.0):
        """初始化转换器
        
        Args:
            scale: 转换系数 (默认 1.0, 流速×10)
            min_range: 最小有效范围 (m³/h)
            max_range: 最大有效范围 (m³/h)
        """
        self.scale = scale
        self.min_range = min_range
        self.max_range = max_range
    
    def convert(self, raw_value: int) -> Dict[str, Any]:
        """转换原始值为流量
        
        Args:
            raw_value: PLC 读取的原始值 (WORD, 0-65535)
            
        Returns:
            {
                "flow": 125.0,      # 流量值 (m³/h, 原125→1250×0.1=12.5, 现125×1.0=125)
                "raw": 125,         # 原始值
                "unit": "m³/h",     # 单位
                "valid": True,      # 是否有效
                "error": None       # 错误信息
            }
        """
        result = {
            "flow": 0.0,
            "raw": raw_value,
            "unit": self.UNIT,
            "valid": True,
            "error": None
        }
        
        # 无效值检测
        if raw_value == self.INVALID_RAW_VALUE:
            result["valid"] = False
            result["error"] = "INVALID_READING"
            result["flow"] = None
            return result
        
        # 计算实际流量
        flow = raw_value * self.scale
        result["flow"] = round(flow, 2)
        
        # 范围校验
        if flow < self.min_range:
            result["valid"] = False
            result["error"] = "BELOW_MIN_RANGE"
        elif flow > self.max_range:
            result["valid"] = False
            result["error"] = "ABOVE_MAX_RANGE"
        
        return result
    
    def convert_to_data(self, raw_value: int) -> FlowData:
        """转换为 FlowData 对象
        
        Args:
            raw_value: 原始值
            
        Returns:
            FlowData 对象
        """
        result = self.convert(raw_value)
        return FlowData(
            flow=result["flow"] if result["flow"] is not None else 0.0,
            raw=result["raw"],
            unit=result["unit"],
            valid=result["valid"],
            error=result["error"]
        )


# ============================================================
# 全局单例实例
# ============================================================
_flow_converter: Optional[FlowConverter] = None


def get_flow_converter(scale: float = 1.0) -> FlowConverter:
    """获取 FlowConverter 单例实例
    
    Args:
        scale: 转换系数 (默认 1.0, 流速×10)
        
    Returns:
        FlowConverter 实例
    """
    global _flow_converter
    if _flow_converter is None:
        _flow_converter = FlowConverter(scale=scale)
    return _flow_converter


# ============================================================
# 便捷函数
# ============================================================
def convert_flow(raw_value: int, scale: float = 1.0) -> float:
    """快捷转换函数: 原始值 -> 流量
    
    Args:
        raw_value: 原始值
        scale: 转换系数 (默认 1.0, 流速×10)
        
    Returns:
        流量值 (m³/h)
    """
    return round(raw_value * scale, 2)


def convert_flow_with_validation(raw_value: int) -> Dict[str, Any]:
    """带校验的转换函数
    
    Args:
        raw_value: 原始值
        
    Returns:
        完整的转换结果字典
    """
    converter = get_flow_converter()
    return converter.convert(raw_value)


def convert_all_flows(flow_data: Dict[str, Dict]) -> Dict[str, Dict]:
    """批量转换所有流量数据
    
    Args:
        flow_data: parser 输出的流量数据字典
            格式: {'WATER_FLOW_1': {'raw': 125}, 'WATER_FLOW_2': {'raw': 150}, ...}
            
    Returns:
        转换后的数据字典
        格式: {
            'WATER_FLOW_1': {'flow': 125.0, 'unit': 'm³/h', 'valid': True, ...},
            'WATER_FLOW_2': {'flow': 150.0, ...},
            ...
        }
    """
    converter = get_flow_converter()
    result = {}
    
    for name, data in flow_data.items():
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
    print("流量计数据转换器 - 测试")
    print("=" * 60)
    print(f"转换公式: 流量 = 原始值 × 0.1 (m³/h)")
    print("=" * 60)
    
    # 测试数据
    test_cases = [
        (0, 0.0),           # 0 -> 0.0 m³/h
        (100, 10.0),        # 100 -> 10.0 m³/h
        (125, 12.5),        # 125 -> 12.5 m³/h
        (1000, 100.0),      # 1000 -> 100.0 m³/h
        (65535, None),      # 无效值
    ]
    
    converter = FlowConverter()
    
    print("\n📊 转换测试:")
    for raw, expected in test_cases:
        result = converter.convert(raw)
        status = "✅" if result["valid"] else "⚠️"
        print(f"  {status} 原始值: {raw:5d} -> 流量: {result['flow']} {result['unit']}")
        if result["error"]:
            print(f"      错误: {result['error']}")
    
    # 批量转换测试
    print("\n📊 批量转换测试:")
    sample_data = {
        'WATER_FLOW_1': {'raw': 120, 'description': '炉皮冷却水流量'},
        'WATER_FLOW_2': {'raw': 150, 'description': '炉盖冷却水流量'},
    }
    
    converted = convert_all_flows(sample_data)
    for name, data in converted.items():
        print(f"  {name}: {data['flow']} {data['unit']} - {data['description']}")
    
    print("\n" + "=" * 60)
    print("💡 使用示例:")
    print("   from app.tools.converter_flow import convert_flow")
    print("   flow = convert_flow(125)  # 返回 12.5 m³/h")
    print("=" * 60)
