# ============================================================
# 文件说明: converter_furnace.py - 电炉数据转换器
# ============================================================
# 功能:
#   1. 将 Parser 解析后的原始数据转换为 InfluxDB 存储格式
#   2. 添加业务上下文 (Tags)
#   3. 执行复杂的业务计算 (如必要)
# ============================================================

from typing import Dict, Any, List
from datetime import datetime

class FurnaceConverter:
    """电炉数据转换器"""
    
    def __init__(self):
        pass
        
    def convert_to_points(self, parsed_data: Dict[str, Any], timestamp: datetime) -> List[Dict[str, Any]]:
        """将解析后的数据转换为 InfluxDB Point 字典列表
        
        Args:
            parsed_data: parser_modbus.parse_all() 的返回结果
            timestamp: 数据生成时间
            
        Returns:
            points: 用于 InfluxDB 写入的字典列表 (measurement, tags, fields, time)
        """
        points = []
        
        # 1. 基础 Tags (目前 DB32 主要是 1号电炉 的数据)
        base_tags = {
            'device_type': 'electric_furnace',
            'device_id': 'furnace_1',  # 暂时硬编码，理想情况应从配置读取映射
            'factory_area': 'L3'
        }
        
        # --------------------------------------------------------
        # 电极深度 (InfraredDistance)
        # --------------------------------------------------------
        electrode_map = {
            'LENTH1': 'electrode_1',
            'LENTH2': 'electrode_2',
            'LENTH3': 'electrode_3'
        }
        for name, data in parsed_data.get('electrode_depths', {}).items():
            if name in electrode_map:
                points.append({
                    'measurement': 'sensor_data',
                    'tags': {
                        **base_tags, 
                        'module_type': 'electrode_depth', 
                        'sensor': electrode_map[name],
                        'plc_variable': name
                    },
                    'fields': {
                        'distance_mm': data['distance'],
                        'high_word': data['high'],
                        'low_word': data['low']
                    },
                    'time': timestamp
                })
                
        # --------------------------------------------------------
        # 冷却水压力 (PressureSensor)
        # --------------------------------------------------------
        pressure_map = {
            'WATER_PRESS_1': 'cooling_water_in',
            'WATER_PRESS_2': 'cooling_water_out'
        }
        for name, data in parsed_data.get('cooling_pressures', {}).items():
            sensor_tag = pressure_map.get(name, name.lower())
            points.append({
                'measurement': 'sensor_data',
                'tags': {
                    **base_tags,
                    'module_type': 'cooling_system',
                    'sensor': sensor_tag,
                    'metric': 'pressure',
                    'plc_variable': name
                },
                'fields': {
                    'value': data['pressure'],
                    'raw': data['raw']
                },
                'time': timestamp
            })

        # --------------------------------------------------------
        # 冷却水流量 (FlowSensor)
        # --------------------------------------------------------
        flow_map = {
            'WATER_FLOW_1': 'cooling_line_1',
            'WATER_FLOW_2': 'cooling_line_2'
        }
        for name, data in parsed_data.get('cooling_flows', {}).items():
            sensor_tag = flow_map.get(name, name.lower())
            points.append({
                'measurement': 'sensor_data',
                'tags': {
                    **base_tags,
                    'module_type': 'cooling_system',
                    'sensor': sensor_tag,
                    'metric': 'flow',
                    'plc_variable': name
                },
                'fields': {
                    'value': data['flow'],
                    'raw': data['raw']
                },
                'time': timestamp
            })

        # --------------------------------------------------------
        # 蝶阀控制状态 (ValveControl)
        # --------------------------------------------------------
        # Ctrl_1 ~ Ctrl_4 对应 8个蝶阀? 
        # 根据 Config: 
        #   Ctrl_1 -> 蝶阀1-2
        #   Ctrl_2 -> 蝶阀3-4 ...
        # Parser中 `parse_valve_control` 返回 open/close/busy bool值
        # 这里仅存储 relay 状态
        for name, data in parsed_data.get('valve_controls', {}).items():
            points.append({
                'measurement': 'sensor_data',
                'tags': {
                    **base_tags,
                    'module_type': 'valve_control',
                    'relay_group': name,
                    'plc_variable': name
                },
                'fields': {
                    'open': int(data['open']),
                    'close': int(data['close']),
                    'busy': int(data['busy']),
                    'raw': data['raw']
                },
                'time': timestamp
            })
            
        return points
