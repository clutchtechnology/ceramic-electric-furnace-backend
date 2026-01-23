# ============================================================
# 文件说明: parser_status_db41.py - DB41 数据状态解析器
# ============================================================
# 解析 DB41 (DataState) 数据状态块:
#   - LENTH1-3: 测距传感器数据状态
#   - WATER_1-2: 流量计数据状态
#   - PRESS_1-2: 压力计数据状态
# ============================================================
# 与 DB30 的区别:
#   - DB30: Modbus 通信状态 (Done/Busy/Error/Status)
#   - DB41: 传感器数据状态 (Error/Status)
# ============================================================

import struct
import yaml
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime


class DataStateParser:
    """DB41 数据状态解析器
    
    解析传感器数据状态，用于监控数据采集健康
    解析后的状态数据保存在内存缓存中，供 API 查询
    """
    
    # 项目根目录
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    
    def __init__(self, config_path: str = None):
        """初始化解析器
        
        Args:
            config_path: 状态配置文件路径
        """
        self.config_path = Path(config_path) if config_path else self.PROJECT_ROOT / "configs" / "status_db41.yaml"
        
        self.db_config: Dict = {}
        self.devices: List[Dict] = []
        self.module_size: int = 4  # 每个状态模块的大小
        
        self._load_config()
    
    def _load_config(self):
        """加载状态配置文件"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            
            # DB 块配置
            db_block = config.get('db_block', {})
            self.db_config = {
                'db_number': db_block.get('db_number', 41),
                'db_name': db_block.get('db_name', 'DataState'),
                'total_size': db_block.get('total_size', 28)  # 7设备×4字节=28
            }
            
            # 状态模块配置
            status_module = config.get('status_module', {})
            self.module_size = status_module.get('module_size', 4)
            
            # 设备列表
            self.devices = config.get('devices', [])
        
        print(f"✅ DB41 数据状态解析器初始化完成: DB{self.db_config['db_number']}, "
              f"{len(self.devices)}个设备, 总大小{self.db_config['total_size']}字节")
    
    def parse_status_module(self, data: bytes, offset: int) -> Dict[str, Any]:
        """解析单个状态模块
        
        DB41 结构 (根据 PLC 截图):
            - Error: Bool @ offset+0 (1位)
            - Status: Word @ offset+2 (2字节)
        
        实际数据可能是:
            - Byte 0: Error (Bool, 只用 Bit 0)
            - Byte 1: 保留
            - Byte 2-3: Status (Word)
        
        Args:
            data: DB41 完整数据
            offset: 模块起始偏移量
            
        Returns:
            解析后的状态数据
        """
        try:
            # 安全边界检查
            if offset + 4 > len(data):
                # 如果数据不足，尝试只读取 Error 字节
                if offset < len(data):
                    error_byte = data[offset]
                    return {
                        'error': bool(error_byte & 0x01),
                        'status': 0,
                        'status_hex': "16#0000",
                        'healthy': not (error_byte & 0x01)
                    }
                else:
                    raise IndexError(f"Offset {offset} out of range")
            
            # 解析 Error 位
            error_byte = data[offset]
            error = bool(error_byte & 0x01)
            
            # 解析 Status 字 (offset+2, 大端序)
            status_offset = offset + 2
            if status_offset + 2 <= len(data):
                status_word = struct.unpack('>H', data[status_offset:status_offset+2])[0]
            else:
                status_word = 0
            
            return {
                'error': error,
                'status': status_word,
                'status_hex': f"16#{status_word:04X}",
                'healthy': not error and status_word == 0
            }
        except Exception as e:
            print(f"⚠️ 解析 DB41 状态模块失败 @ offset {offset}: {e}")
            return {
                'error': True,
                'status': 0xFFFF,
                'status_hex': "16#FFFF",
                'healthy': False
            }
    
    def parse_all(self, db41_data: bytes) -> Dict[str, Any]:
        """解析 DB41 所有状态数据
        
        Args:
            db41_data: DB41 完整字节数据
            
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
                status = self.parse_status_module(db41_data, offset)
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
                print(f"⚠️ 解析设备状态失败 [{device_id}]: {e}")
                result['devices'][device_id] = {
                    'error': True,
                    'status': 0xFFFF,
                    'status_hex': "16#FFFF",
                    'healthy': False,
                    'device_name': device.get('device_name', ''),
                    'plc_name': device.get('plc_name', ''),
                    'parse_error': str(e)
                }
                result['summary']['error'] += 1
        
        return result
    
    def get_device_list(self) -> List[Dict]:
        """获取设备列表"""
        return [
            {
                'device_id': d.get('device_id'),
                'device_name': d.get('device_name'),
                'plc_name': d.get('plc_name'),
                'data_device_id': d.get('data_device_id'),
                'enabled': d.get('enabled', True)
            }
            for d in self.devices
        ]
    
    def get_db_number(self) -> int:
        """获取 DB 块号"""
        return self.db_config.get('db_number', 41)
    
    def get_total_size(self) -> int:
        """获取 DB 块总大小 (字节)"""
        return self.db_config.get('total_size', 28)


# 测试代码
if __name__ == "__main__":
    parser = DataStateParser()
    
    # 模拟 DB41 数据 (28字节 = 7设备 × 4字节)
    test_data = bytearray(28)
    
    # LENTH1 @ 0: 正常
    test_data[0] = 0x00  # Error = false
    test_data[2:4] = struct.pack('>H', 0x0000)  # Status = 0
    
    # LENTH2 @ 4: 正常
    test_data[4] = 0x00
    test_data[6:8] = struct.pack('>H', 0x0000)
    
    # LENTH3 @ 8: 错误
    test_data[8] = 0x01  # Error = true
    test_data[10:12] = struct.pack('>H', 0x8001)  # Status = 错误码
    
    result = parser.parse_all(bytes(test_data))
    print("\n解析结果:")
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
