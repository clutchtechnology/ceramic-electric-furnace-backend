# ============================================================
# 文件说明: parser_modbus.py - DB32 Modbus 数据解析器
# ============================================================
# 解析 DB32 (MODBUS_DATA_VALUE) 数据块:
#   - 3个红外测距 (LENTH1-3): 电极深度
#   - 2个压力计 (WATER_PRESS_1-2): 冷却水压力
#   - 2个流量计 (WATER_FLOW_1-2): 冷却水流量
#   - 4个蝶阀控制 (Ctrl_1-4): 继电器状态
#   - MBrly: 写入寄存器 (不解析，不存储)
# ============================================================

import struct
import yaml
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime


class ModbusDataParser:
    """DB32 Modbus 数据解析器
    
    负责解析 DB32 (MODBUS_DATA_VALUE) 数据块中的传感器数据
    """
    
    # 项目根目录
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    
    def __init__(self, 
                 config_path: str = None,
                 module_path: str = None):
        """初始化解析器
        
        Args:
            config_path: 设备配置文件路径
            module_path: 基础模块配置文件路径
        """
        self.config_path = Path(config_path) if config_path else self.PROJECT_ROOT / "configs" / "config_L3_P2_F2_C4.yaml"
        self.module_path = Path(module_path) if module_path else self.PROJECT_ROOT / "configs" / "plc_modules.yaml"
        
        self.config: Dict = {}
        self.base_modules: Dict = {}
        self.db_config: Dict = {}
        self.modules: List[Dict] = []
        
        self._load_config()
    
    def _load_config(self):
        """加载配置文件"""
        # 加载基础模块定义
        with open(self.module_path, 'r', encoding='utf-8') as f:
            module_config = yaml.safe_load(f)
            self.base_modules = module_config.get('modules', {})
        
        # 加载设备配置
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
            
            # 获取 DB32 配置
            db32 = self.config.get('db32_modbus', {})
            self.db_config = {
                'db_number': db32.get('db_block', 32),
                'db_name': db32.get('name', 'MODBUS_DATA_VALUE'),
                'total_size': db32.get('total_size', 29)
            }
            self.modules = db32.get('modules', [])
        
        print(f"✅ DB32 解析器初始化完成: DB{self.db_config['db_number']}, "
              f"{len(self.modules)}个模块, 总大小{self.db_config['total_size']}字节")
    
    def _get_module_def(self, module_ref: str) -> Optional[Dict]:
        """获取基础模块定义"""
        return self.base_modules.get(module_ref)
    
    def parse_infrared_distance(self, data: bytes, offset: int) -> Dict[str, Any]:
        """解析红外测距数据 (4字节: HIGH + LOW)
        
        Args:
            data: DB32 完整数据
            offset: 模块起始偏移量
            
        Returns:
            解析后的数据 {'high': int, 'low': int, 'distance': float}
        """
        try:
            high = struct.unpack('>H', data[offset:offset+2])[0]
            low = struct.unpack('>H', data[offset+2:offset+4])[0]
            # 组合高低位得到实际距离值 (mm)
            distance = (high << 16) | low
            return {
                'high': high,
                'low': low,
                'distance': float(distance),
                'unit': 'mm'
            }
        except Exception as e:
            print(f"⚠️ 解析红外测距失败 @ offset {offset}: {e}")
            return {'high': 0, 'low': 0, 'distance': 0.0, 'unit': 'mm'}
    
    def parse_pressure(self, data: bytes, offset: int, scale: float = 0.01) -> Dict[str, Any]:
        """解析压力数据 (2字节: WORD)
        
        Args:
            data: DB32 完整数据
            offset: 模块起始偏移量
            scale: 缩放系数 (默认 0.01, 即原始值/100 得到 MPa)
            
        Returns:
            解析后的数据 {'raw': int, 'pressure': float}
        """
        try:
            raw = struct.unpack('>H', data[offset:offset+2])[0]
            pressure = raw * scale
            return {
                'raw': raw,
                'pressure': round(pressure, 3),
                'unit': 'MPa'
            }
        except Exception as e:
            print(f"⚠️ 解析压力失败 @ offset {offset}: {e}")
            return {'raw': 0, 'pressure': 0.0, 'unit': 'MPa'}
    
    def parse_flow(self, data: bytes, offset: int, scale: float = 0.01) -> Dict[str, Any]:
        """解析流量数据 (2字节: WORD)
        
        Args:
            data: DB32 完整数据
            offset: 模块起始偏移量
            scale: 缩放系数 (默认 0.01)
            
        Returns:
            解析后的数据 {'raw': int, 'flow': float}
        """
        try:
            raw = struct.unpack('>H', data[offset:offset+2])[0]
            flow = raw * scale
            return {
                'raw': raw,
                'flow': round(flow, 2),
                'unit': 'm³/h'
            }
        except Exception as e:
            print(f"⚠️ 解析流量失败 @ offset {offset}: {e}")
            return {'raw': 0, 'flow': 0.0, 'unit': 'm³/h'}
    
    def parse_valve_control(self, data: bytes, offset: int) -> Dict[str, Any]:
        """解析蝶阀控制状态 (2字节: WORD, 位操作)
        
        Args:
            data: DB32 完整数据
            offset: 模块起始偏移量
            
        Returns:
            解析后的数据 {'open': bool, 'close': bool, 'busy': bool, 'raw': int}
        """
        try:
            raw = struct.unpack('>H', data[offset:offset+2])[0]
            # 位解析: bit0=OPEN, bit1=CLOSE, bit2=BUSY
            return {
                'raw': raw,
                'open': bool(raw & 0x01),
                'close': bool(raw & 0x02),
                'busy': bool(raw & 0x04)
            }
        except Exception as e:
            print(f"⚠️ 解析蝶阀状态失败 @ offset {offset}: {e}")
            return {'raw': 0, 'open': False, 'close': False, 'busy': False}
    
    def parse_all(self, db32_data: bytes) -> Dict[str, Any]:
        """解析 DB32 所有数据 (不包括 MBrly 写入寄存器)
        
        Args:
            db32_data: DB32 完整字节数据 (至少28字节, MBrly不解析)
            
        Returns:
            解析后的完整数据结构
        """
        timestamp = datetime.now().isoformat()
        
        result = {
            'timestamp': timestamp,
            'db_block': self.db_config['db_number'],
            'electrode_depths': {},    # 3个红外测距
            'cooling_pressures': {},   # 2个压力计
            'cooling_flows': {},       # 2个流量计
            'valve_controls': {}       # 4个蝶阀控制
        }
        
        for module in self.modules:
            name = module.get('name', '')
            module_ref = module.get('module_ref', '')
            offset = module.get('offset', 0)
            
            # 跳过 MBrly (写入寄存器，不解析)
            if module_ref == 'RelayWriteArray' or name == 'MBrly':
                continue
            
            try:
                if module_ref == 'InfraredDistance' or name.startswith('LENTH'):
                    parsed = self.parse_infrared_distance(db32_data, offset)
                    result['electrode_depths'][name] = parsed
                
                elif module_ref == 'PressureSensor' or name.startswith('WATER_PRESS'):
                    parsed = self.parse_pressure(db32_data, offset)
                    result['cooling_pressures'][name] = parsed
                
                elif module_ref == 'FlowSensor' or name.startswith('WATER_FLOW'):
                    parsed = self.parse_flow(db32_data, offset)
                    result['cooling_flows'][name] = parsed
                
                elif module_ref == 'ValveControl' or name.startswith('Ctrl'):
                    parsed = self.parse_valve_control(db32_data, offset)
                    result['valve_controls'][name] = parsed
                    
            except Exception as e:
                print(f"⚠️ 解析模块 {name} 失败: {e}")
        
        return result
    
    def get_db_number(self) -> int:
        """获取 DB 块号"""
        return self.db_config['db_number']
    
    def get_total_size(self) -> int:
        """获取 DB 块总大小
        
        Config 中通常定义为 29 bytes (覆盖到 28.7 的 MBrly)
        从 config 读取, 默认为 29
        """
        return self.db_config.get('total_size', 29)


# ============================================================
# 使用示例
# ============================================================
if __name__ == "__main__":
    parser = ModbusDataParser()
    
    # 模拟 DB32 数据 (29字节)
    test_data = bytes([
        # LENTH1 (offset 0-3): 红外测距1
        0x00, 0x01, 0x03, 0xE8,  # HIGH=1, LOW=1000 -> distance=66536
        # LENTH2 (offset 4-7): 红外测距2
        0x00, 0x02, 0x07, 0xD0,  # HIGH=2, LOW=2000
        # LENTH3 (offset 8-11): 红外测距3
        0x00, 0x03, 0x0B, 0xB8,  # HIGH=3, LOW=3000
        # WATER_PRESS_1 (offset 12-13): 压力1
        0x01, 0xF4,  # 500 -> 5.00 MPa
        # WATER_PRESS_2 (offset 14-15): 压力2
        0x02, 0x58,  # 600 -> 6.00 MPa
        # WATER_FLOW_1 (offset 16-17): 流量1
        0x03, 0xE8,  # 1000 -> 10.00 m³/h
        # WATER_FLOW_2 (offset 18-19): 流量2
        0x04, 0xB0,  # 1200 -> 12.00 m³/h
        # Ctrl_1 (offset 20-21): 蝶阀控制1
        0x00, 0x01,  # OPEN=true
        # Ctrl_2 (offset 22-23): 蝶阀控制2
        0x00, 0x02,  # CLOSE=true
        # Ctrl_3 (offset 24-25): 蝶阀控制3
        0x00, 0x04,  # BUSY=true
        # Ctrl_4 (offset 26-27): 蝶阀控制4
        0x00, 0x00,  # 全部 false
        # MBrly (offset 28): 写入寄存器 (不解析)
        0x00
    ])
    
    result = parser.parse_all(test_data)
    
    print("\n📊 DB32 解析结果:")
    print(f"时间戳: {result['timestamp']}")
    
    print("\n🔭 电极深度 (红外测距):")
    for name, data in result['electrode_depths'].items():
        print(f"  {name}: {data['distance']} {data['unit']}")
    
    print("\n💧 冷却水压力:")
    for name, data in result['cooling_pressures'].items():
        print(f"  {name}: {data['pressure']} {data['unit']}")
    
    print("\n🌊 冷却水流量:")
    for name, data in result['cooling_flows'].items():
        print(f"  {name}: {data['flow']} {data['unit']}")
    
    print("\n🔧 蝶阀控制状态:")
    for name, data in result['valve_controls'].items():
        print(f"  {name}: OPEN={data['open']}, CLOSE={data['close']}, BUSY={data['busy']}")
