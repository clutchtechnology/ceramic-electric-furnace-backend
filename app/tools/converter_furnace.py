# ============================================================
# 文件说明: converter_furnace.py - 电炉数据转换器
# ============================================================
# 功能:
#   1. 将 Parser 解析后的原始数据转换为 InfluxDB 存储格式
#   2. 添加业务上下文 (Tags)
#   3. 执行复杂的业务计算 (如必要)
# ============================================================
# 【数据库写入说明 - DB32 传感器数据】
# ============================================================
# Measurement: sensor_data
# Tags:
#   - device_type: electric_furnace
#   - device_id: furnace_1
#   - factory_area: L3
#   - module_type: electrode_depth / cooling_system / cooling_water_total
#   - sensor: electrode_1/2/3 / cooling_water_in/out / cooling_line_1/2
#   - batch_code: 批次号 (动态)
# Fields (按 module_type 分类):
# ============================================================
# module_type=electrode_depth (电极深度):
#   - distance_mm: 电极深度 (mm)
#   - high_word: 高字 (原始值)
#   - low_word: 低字 (原始值)
# ============================================================
# module_type=cooling_system, metric=pressure (冷却水压力):
#   - value: 压力值 (kPa, 原始值×0.01)
#   - raw: 原始值
# ============================================================
# module_type=cooling_system, metric=flow (冷却水流量):
#   - value: 流量值 (m³/h)
#   - raw: 原始值
# ============================================================
# module_type=cooling_water_total (冷却水累计 - 在 polling_data_processor.py 中添加):
#   - furnace_shell_water_total: 炉皮累计流量 (m³)
#   - furnace_cover_water_total: 炉盖累计流量 (m³)
# ============================================================

from typing import Dict, Any, List
from datetime import datetime

class FurnaceConverter:
    """电炉数据转换器"""
    
    def __init__(self):
        pass
        
    # ============================================================
    # 1: 数据转换主函数
    # ============================================================
    def convert_to_points(self, parsed_data: Dict[str, Any], timestamp: datetime, batch_code: str = None) -> List[Dict[str, Any]]:
        """将解析后的数据转换为 InfluxDB Point 字典列表
        
        Args:
            parsed_data: parser_modbus.parse_all() 的返回结果
            timestamp: 数据生成时间
            batch_code: 批次号 (用于追踪冶炼轮次)
            
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
        
        # 添加批次号 tag
        if batch_code:
            base_tags['batch_code'] = batch_code
        
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
                # 计算高低字 (如果需要兼容旧有的字段)
                distance_val = data.get('distance', 0) or 0
                high_word = (distance_val >> 16) & 0xFFFF
                low_word = distance_val & 0xFFFF
                
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
                        'high_word': high_word,
                        'low_word': low_word
                    },
                    'time': timestamp
                })
                
        # --------------------------------------------------------
        # 冷却水压力 (PressureSensor)
        # 单位: kPa (转换系数 0.01)
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
                    'value': data['pressure'],  # kPa
                    'raw': data['raw']
                },
                'time': timestamp
            })

        # --------------------------------------------------------
        # 冷却水流量 (FlowSensor)
        # 单位: m³/h (转换系数 1.0)
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
                    'value': data['flow'],  # m³/h
                    'raw': data['raw']
                },
                'time': timestamp
            })

        # --------------------------------------------------------
        # 蝶阀状态监测 (ValveStatusMonitor)
        # --------------------------------------------------------
        # 暂时不写入 InfluxDB，仅存内存缓存供 API 读取
        # valve_status = parsed_data.get('valve_status', {})
        # if valve_status:
        #     points.append({
        #         'measurement': 'sensor_data',
        #         'tags': {
        #             **base_tags,
        #             'module_type': 'valve_status',
        #             'plc_variable': 'ValveStatus'
        #         },
        #         'fields': {
        #             'status_byte': valve_status.get('status_byte', 0),
        #             'valve_1_state': valve_status.get('valve_1_state', 'STOPPED'),
        #             'valve_2_state': valve_status.get('valve_2_state', 'STOPPED'),
        #             'valve_3_state': valve_status.get('valve_3_state', 'STOPPED'),
        #             'valve_4_state': valve_status.get('valve_4_state', 'STOPPED'),
        #             'open_count': valve_status.get('open_count', 0)
        #         },
        #         'time': timestamp
        #     })
            
        return points
