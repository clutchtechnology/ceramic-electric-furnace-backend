# ============================================================
# 文件说明: converter_length.py - 红外测距传感器数据转换器
# ============================================================
# 功能:
#   1. 将红外测距传感器的高低位 WORD 组合为实际测量值
#   2. 根据手册规格进行数据校验和单位转换
# ============================================================
# 数据格式 (根据手册):
#   - 功能码: 03H (读取保持寄存器)
#   - 0000H: 高16位 (HIGH WORD)
#   - 0001H: 低16位 (LOW WORD)
#   - 组合公式: 测量值 = (HIGH << 16) | LOW
#   - 单位: mm (毫米)
#   - 数据类型: 32位无符号整数 (DWORD)
# ============================================================

from typing import Dict, Any, Optional, Tuple


class LengthConverter:
    """红外测距传感器数据转换器
    
    将高低16位 WORD 组合为32位测量值 (单位: mm)
    """
    
    # 传感器规格常量 (可根据实际手册调整)
    MIN_VALID_DISTANCE_MM = 0       # 最小有效距离 (mm)
    MAX_VALID_DISTANCE_MM = 5000    # 最大有效距离 (mm) - 根据实际传感器量程调整
    INVALID_VALUE = 0xFFFFFFFF      # 无效数据标识
    
    def __init__(self, 
                 min_range_mm: int = 0, 
                 max_range_mm: int = 5000,
                 unit: str = "mm"):
        """初始化转换器
        
        Args:
            min_range_mm: 传感器最小量程 (mm)
            max_range_mm: 传感器最大量程 (mm)
            unit: 输出单位 (默认 mm)
        """
        self.min_range = min_range_mm
        self.max_range = max_range_mm
        self.unit = unit
    
    @staticmethod
    def combine_words(high: int, low: int) -> int:
        """将高低位 WORD 组合为 32 位整数
        
        Args:
            high: 高16位 (WORD, 0x0000-0xFFFF)
            low: 低16位 (WORD, 0x0000-0xFFFF)
            
        Returns:
            32位无符号整数
        """
        # 确保输入在有效范围内
        high = high & 0xFFFF
        low = low & 0xFFFF
        return (high << 16) | low
    
    @staticmethod
    def split_to_words(value: int) -> Tuple[int, int]:
        """将32位整数拆分为高低位 WORD (用于调试/验证)
        
        Args:
            value: 32位整数
            
        Returns:
            (high, low) 元组
        """
        high = (value >> 16) & 0xFFFF
        low = value & 0xFFFF
        return high, low
    
    def convert(self, high: int, low: int) -> Dict[str, Any]:
        """转换高低位 WORD 为测量距离
        
        Args:
            high: 高16位原始值
            low: 低16位原始值
            
        Returns:
            Dict 包含:
                - distance: 测量距离 (mm)
                - high: 原始高位值
                - low: 原始低位值
                - raw: 组合后的原始32位值
                - unit: 单位
                - valid: 数据是否有效
                - error: 错误信息 (如有)
        """
        # 组合为32位值
        raw_value = self.combine_words(high, low)
        
        result = {
            'distance': raw_value,
            'high': high,
            'low': low,
            'raw': raw_value,
            'unit': self.unit,
            'valid': True,
            'error': None
        }
        
        # 数据有效性校验
        if raw_value == self.INVALID_VALUE:
            result['valid'] = False
            result['error'] = 'INVALID_READING'
            result['distance'] = None
        elif raw_value < self.min_range:
            result['valid'] = False
            result['error'] = 'BELOW_MIN_RANGE'
        elif raw_value > self.max_range:
            result['valid'] = False
            result['error'] = 'ABOVE_MAX_RANGE'
            
        return result
    
    def convert_to_meters(self, high: int, low: int) -> float:
        """转换为米 (m)
        
        Args:
            high: 高16位原始值
            low: 低16位原始值
            
        Returns:
            距离值 (米)
        """
        raw_value = self.combine_words(high, low)
        return raw_value / 1000.0
    
    def convert_to_centimeters(self, high: int, low: int) -> float:
        """转换为厘米 (cm)
        
        Args:
            high: 高16位原始值
            low: 低16位原始值
            
        Returns:
            距离值 (厘米)
        """
        raw_value = self.combine_words(high, low)
        return raw_value / 10.0


# ============================================================
# 全局单例实例
# ============================================================
_length_converter: Optional[LengthConverter] = None


def get_length_converter(
    min_range_mm: int = 0,
    max_range_mm: int = 5000
) -> LengthConverter:
    """获取 LengthConverter 单例实例
    
    Args:
        min_range_mm: 传感器最小量程
        max_range_mm: 传感器最大量程
        
    Returns:
        LengthConverter 实例
    """
    global _length_converter
    if _length_converter is None:
        _length_converter = LengthConverter(
            min_range_mm=min_range_mm,
            max_range_mm=max_range_mm
        )
    return _length_converter


def convert_electrode_depth(high: int, low: int) -> Dict[str, Any]:
    """便捷函数: 转换电极深度测量值
    
    Args:
        high: 高16位原始值
        low: 低16位原始值
        
    Returns:
        转换结果字典
    """
    converter = get_length_converter()
    return converter.convert(high, low)


# ============================================================
# 批量转换函数 (用于 Parser 输出 -> 前端数据格式)
# ============================================================
def convert_all_electrode_depths(parsed_electrode_data: Dict[str, Dict]) -> Dict[str, Any]:
    """批量转换所有电极深度数据
    
    Args:
        parsed_electrode_data: parser_config_db32 输出的 electrode_depths 字典
            格式: {'LENTH1': {'high': x, 'low': y}, 'LENTH2': {...}, ...}
            
    Returns:
        转换后的数据字典，适合前端显示
        格式: {
            'LENTH1': {'distance_mm': 1234, 'distance_m': 1.234, 'valid': True, ...},
            'LENTH2': {...},
            ...
        }
    """
    converter = get_length_converter()
    result = {}
    
    for name, data in parsed_electrode_data.items():
        high = data.get('high', 0)
        low = data.get('low', 0)
        
        converted = converter.convert(high, low)
        
        # 添加额外的单位转换
        if converted['valid'] and converted['distance'] is not None:
            converted['distance_mm'] = converted['distance']
            converted['distance_m'] = converted['distance'] / 1000.0
            converted['distance_cm'] = converted['distance'] / 10.0
        else:
            converted['distance_mm'] = None
            converted['distance_m'] = None
            converted['distance_cm'] = None
            
        result[name] = converted
        
    return result


# ============================================================
# 示例/测试代码
# ============================================================
if __name__ == "__main__":
    # 测试数据
    test_cases = [
        (0x0000, 0x04D2, 1234),      # 1234 mm
        (0x0001, 0x0000, 65536),     # 65536 mm = 65.536 m
        (0x0000, 0x0000, 0),         # 0 mm
        (0xFFFF, 0xFFFF, 0xFFFFFFFF),# 无效值
    ]
    
    converter = LengthConverter()
    
    print("=" * 60)
    print("红外测距传感器数据转换测试")
    print("=" * 60)
    
    for high, low, expected in test_cases:
        result = converter.convert(high, low)
        print(f"\nHIGH=0x{high:04X}, LOW=0x{low:04X}")
        print(f"  预期值: {expected}")
        print(f"  实际值: {result['raw']}")
        print(f"  距离: {result['distance']} {result['unit']}")
        print(f"  有效: {result['valid']}")
        if result['error']:
            print(f"  错误: {result['error']}")
