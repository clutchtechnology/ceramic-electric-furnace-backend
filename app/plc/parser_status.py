# ============================================================
# 文件说明: parser_status.py - DB30 Modbus 状态解析器
# ============================================================
# 解析 DB30 (MODBUS_DB_Value) 状态数据块:
#   - 通信状态 (MB_COMM)
#   - 蝶阀写入状态 (MB_MASTER_WRITE_1)
#   - 3个测距通信状态 (MB_MASTER_LENTH_1-3)
#   - 2个流量计通信状态 (MB_MASTER_WATER_1-2)
#   - 2个压力计通信状态 (MB_MASTER_PRESS_1-2)
#   - 继电器读取状态 (DB_MASTER_RELAY)
# ============================================================

import struct
import yaml
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime


class ModbusStatusParser:
    """DB30 Modbus 状态解析器
    
    解析 Modbus Master 通信状态，用于监控通信健康
    解析后的状态数据保存在内存缓存中，供 API 查询
    """
    
    # 项目根目录
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    
    def __init__(self, config_path: str = None):
        """初始化解析器
        
        Args:
            config_path: 状态配置文件路径
        """
        self.config_path = Path(config_path) if config_path else self.PROJECT_ROOT / "configs" / "status_L3_P2_F2_C4_db30.yaml"
        
        self.db_config: Dict = {}
        self.devices: List[Dict] = []
        self.module_size: int = 4  # 每个状态模块 4 字节
        
        self._load_config()
    
    def _load_config(self):
        """加载状态配置文件"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            
            # DB 块配置
            db_block = config.get('db_block', {})
            self.db_config = {
                'db_number': db_block.get('db_number', 30),
                'db_name': db_block.get('db_name', 'MODBUS_DB_Value'),
                'total_size': db_block.get('total_size', 40)
            }
            
            # 状态模块配置
            status_module = config.get('status_module', {})
            self.module_size = status_module.get('module_size', 4)
            
            # 设备列表
            self.devices = config.get('devices', [])
        
        print(f"✅ DB30 状态解析器初始化完成: DB{self.db_config['db_number']}, "
              f"{len(self.devices)}个设备, 总大小{self.db_config['total_size']}字节")
    
    def parse_status_module(self, data: bytes, offset: int) -> Dict[str, Any]:
        """解析单个状态模块 (4字节)
        
        结构:
            - Byte 0: Bit0=Done, Bit1=Busy, Bit2=Error
            - Byte 1: 保留
            - Byte 2-3: Status (WORD)
        
        Args:
            data: DB30 完整数据
            offset: 模块起始偏移量
            
        Returns:
            解析后的状态数据
        """
        try:
            byte0 = data[offset]
            status_word = struct.unpack('>H', data[offset+2:offset+4])[0]
            
            return {
                'done': bool(byte0 & 0x01),
                'busy': bool(byte0 & 0x02),
                'error': bool(byte0 & 0x04),
                'status': status_word,
                'status_hex': f"16#{status_word:04X}",
                'healthy': not (byte0 & 0x04) and status_word == 0
            }
        except Exception as e:
            print(f"⚠️ 解析状态模块失败 @ offset {offset}: {e}")
            return {
                'done': False,
                'busy': False,
                'error': True,
                'status': 0xFFFF,
                'status_hex': "16#FFFF",
                'healthy': False
            }
    
    def parse_all(self, db30_data: bytes) -> Dict[str, Any]:
        """解析 DB30 所有状态数据
        
        Args:
            db30_data: DB30 完整字节数据 (至少40字节)
            
        Returns:
            解析后的完整状态数据结构
        """
        timestamp = datetime.now().isoformat()
        
        result = {
            'timestamp': timestamp,
            'db_block': self.db_config['db_number'],
            'devices': {},
            'summary': {
                'total': len(self.devices),
                'healthy': 0,
                'error': 0
            }
        }
        
        for device in self.devices:
            device_id = device.get('device_id', '')
            offset = device.get('start_offset', 0)
            enabled = device.get('enabled', True)
            
            if not enabled:
                continue
            
            try:
                status = self.parse_status_module(db30_data, offset)
                status['device_name'] = device.get('device_name', '')
                status['plc_name'] = device.get('plc_name', '')
                status['data_device_id'] = device.get('data_device_id', '')
                status['description'] = device.get('description', '')
                
                result['devices'][device_id] = status
                
                # 统计
                if status['healthy']:
                    result['summary']['healthy'] += 1
                else:
                    result['summary']['error'] += 1
                    
            except Exception as e:
                print(f"⚠️ 解析设备 {device_id} 状态失败: {e}")
                result['devices'][device_id] = {
                    'device_name': device.get('device_name', ''),
                    'error': True,
                    'healthy': False,
                    'parse_error': str(e)
                }
                result['summary']['error'] += 1
        
        return result
    
    def get_db_number(self) -> int:
        """获取 DB 块号"""
        return self.db_config['db_number']
    
    def get_total_size(self) -> int:
        """获取 DB 块总大小"""
        return self.db_config['total_size']
    
    def get_device_list(self) -> List[Dict[str, str]]:
        """获取设备列表"""
        return [
            {
                'device_id': dev['device_id'],
                'device_name': dev.get('device_name', ''),
                'plc_name': dev.get('plc_name', ''),
                'data_device_id': dev.get('data_device_id', '')
            }
            for dev in self.devices if dev.get('enabled', True)
        ]


# ============================================================
# 使用示例
# ============================================================
if __name__ == "__main__":
    parser = ModbusStatusParser()
    
    print("\n📋 设备状态列表:")
    for dev in parser.get_device_list():
        print(f"  - {dev['device_id']}: {dev['device_name']} ({dev['plc_name']})")
    
    # 模拟 DB30 数据 (40字节)
    test_data = bytes([
        # status_comm (offset 0): Done=true, 正常
        0x01, 0x00, 0x00, 0x00,
        # status_write_valve (offset 4): Busy=true
        0x02, 0x00, 0x00, 0x00,
        # status_lenth_1 (offset 8): Done=true, 正常
        0x01, 0x00, 0x00, 0x00,
        # status_lenth_2 (offset 12): Error=true, 状态=0x8001
        0x04, 0x00, 0x80, 0x01,
        # status_lenth_3 (offset 16): Done=true, 正常
        0x01, 0x00, 0x00, 0x00,
        # status_flow_1 (offset 20): Done=true, 正常
        0x01, 0x00, 0x00, 0x00,
        # status_flow_2 (offset 24): Done=true, 正常
        0x01, 0x00, 0x00, 0x00,
        # status_press_1 (offset 28): Done=true, 正常
        0x01, 0x00, 0x00, 0x00,
        # status_press_2 (offset 32): Done=true, 正常
        0x01, 0x00, 0x00, 0x00,
        # status_relay_read (offset 36): Done=true, 正常
        0x01, 0x00, 0x00, 0x00,
    ])
    
    result = parser.parse_all(test_data)
    
    print(f"\n📊 DB30 状态解析结果:")
    print(f"时间戳: {result['timestamp']}")
    print(f"总计: {result['summary']['total']} 个设备, "
          f"正常: {result['summary']['healthy']}, 异常: {result['summary']['error']}")
    
    print("\n🔍 各设备状态:")
    for device_id, status in result['devices'].items():
        health_icon = "✅" if status.get('healthy') else "❌"
        print(f"  {health_icon} {device_id}: {status.get('device_name', '')}")
        print(f"      Done={status.get('done')}, Busy={status.get('busy')}, "
              f"Error={status.get('error')}, Status={status.get('status_hex')}")
