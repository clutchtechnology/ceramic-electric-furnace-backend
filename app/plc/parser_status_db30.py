# ============================================================
# 文件说明: parser_status_db30.py - DB30 配置驱动状态解析器
# ============================================================
# 功能:
#   1. 根据 YAML 配置文件自动解析 DB30 通信状态数据
#   2. 解析 Modbus Master 指令的 Done/Busy/Error/Status 状态
#   3. 支持多设备状态汇总
#   4. 提供健康检查摘要
# ============================================================

import struct
import yaml
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime


class ConfigDrivenDB30Parser:
    """配置驱动的 DB30 状态解析器
    
    根据 status_L3_P2_F2_C4_db30.yaml 中的设备定义，
    自动解析 PLC DB30 数据块中的通信状态。
    """
    
    # 项目根目录
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    
    def __init__(self, 
                 config_path: str = None,
                 modules_path: str = None):
        """初始化解析器
        
        Args:
            config_path: DB30 状态配置文件路径
            modules_path: 基础模块定义文件路径
        """
        self.config_path = Path(config_path) if config_path else \
            self.PROJECT_ROOT / "configs" / "status_L3_P2_F2_C4_db30.yaml"
        self.modules_path = Path(modules_path) if modules_path else \
            self.PROJECT_ROOT / "configs" / "plc_modules.yaml"
        
        # 配置数据
        self.config: Dict[str, Any] = {}
        self.status_modules: Dict[str, Dict] = {}
        self.db_config: Dict[str, Any] = {}
        self.devices: List[Dict] = []
        self.module_size: int = 4  # 默认状态模块大小
        
        self._load_config()
    
    def _load_config(self):
        """加载配置文件"""
        # 1. 加载基础模块定义 (status_modules 部分)
        with open(self.modules_path, 'r', encoding='utf-8') as f:
            modules_config = yaml.safe_load(f)
            self.status_modules = modules_config.get('status_modules', {})
        
        # 2. 加载 DB30 状态配置
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        # 3. 提取 DB 块配置
        db_block = self.config.get('db_block', {})
        self.db_config = {
            'db_number': db_block.get('db_number', 30),
            'db_name': db_block.get('db_name', 'MODBUS_DB_Value'),
            'total_size': db_block.get('total_size', 40),
            'description': db_block.get('description', '')
        }
        
        # 4. 提取状态模块配置
        status_module = self.config.get('status_module', {})
        self.module_size = status_module.get('module_size', 4)
        
        # 5. 提取设备列表
        self.devices = self.config.get('devices', [])
        
        print(f"✅ DB30 状态解析器初始化: DB{self.db_config['db_number']}, "
              f"{len(self.devices)}个设备, 模块大小{self.module_size}字节")
    
    def _get_status_module_definition(self, module_ref: str) -> Optional[Dict]:
        """获取状态模块定义"""
        return self.status_modules.get(module_ref)
    
    def parse_status_module(self, data: bytes, offset: int) -> Dict[str, Any]:
        """解析单个状态模块 (4字节标准格式)
        
        结构:
            - Byte 0: bit0=Done, bit1=Busy, bit2=Error
            - Byte 1: 保留
            - Byte 2-3: Status (WORD, Big Endian)
        
        Args:
            data: 完整的 DB 块数据
            offset: 模块起始偏移量
        
        Returns:
            解析后的状态数据
        """
        if offset + 4 > len(data):
            return {
                'done': False,
                'busy': False,
                'error': True,
                'status': 0xFFFF,
                'status_hex': '16#FFFF',
                'healthy': False,
                'parse_error': '数据长度不足'
            }
        
        try:
            byte0 = data[offset]
            status_word = struct.unpack('>H', data[offset + 2:offset + 4])[0]
            
            done = bool(byte0 & 0x01)
            busy = bool(byte0 & 0x02)
            error = bool(byte0 & 0x04)
            
            # 健康判定: 没有错误且状态码为 0
            healthy = not error and status_word == 0
            
            return {
                'done': done,
                'busy': busy,
                'error': error,
                'status': status_word,
                'status_hex': f'16#{status_word:04X}',
                'healthy': healthy
            }
            
        except Exception as e:
            return {
                'done': False,
                'busy': False,
                'error': True,
                'status': 0xFFFF,
                'status_hex': '16#FFFF',
                'healthy': False,
                'parse_error': str(e)
            }
    
    def parse_device(self, data: bytes, device_config: Dict) -> Dict[str, Any]:
        """解析单个设备状态
        
        Args:
            data: 完整的 DB 块数据
            device_config: 设备配置
        
        Returns:
            解析后的设备状态
        """
        device_id = device_config.get('device_id', '')
        device_name = device_config.get('device_name', '')
        plc_name = device_config.get('plc_name', '')
        offset = device_config.get('start_offset', 0)
        enabled = device_config.get('enabled', True)
        data_device_id = device_config.get('data_device_id', '')
        description = device_config.get('description', '')
        
        if not enabled:
            return {
                'device_id': device_id,
                'device_name': device_name,
                'enabled': False,
                'skipped': True
            }
        
        # 解析状态模块
        status = self.parse_status_module(data, offset)
        
        return {
            'device_id': device_id,
            'device_name': device_name,
            'plc_name': plc_name,
            'offset': offset,
            'data_device_id': data_device_id,
            'description': description,
            **status
        }
    
    def parse_all(self, db30_data: bytes) -> Dict[str, Any]:
        """解析 DB30 所有设备状态
        
        Args:
            db30_data: DB30 完整字节数据
        
        Returns:
            解析后的完整状态数据
        """
        timestamp = datetime.now().isoformat()
        
        result = {
            'timestamp': timestamp,
            'db_block': self.db_config['db_number'],
            'db_name': self.db_config['db_name'],
            'data_size': len(db30_data),
            'devices': {},
            'summary': {
                'total': 0,
                'healthy': 0,
                'error': 0,
                'busy': 0,
                'skipped': 0
            }
        }
        
        for device_config in self.devices:
            device_id = device_config.get('device_id', '')
            parsed = self.parse_device(db30_data, device_config)
            result['devices'][device_id] = parsed
            
            # 统计
            if parsed.get('skipped'):
                result['summary']['skipped'] += 1
            else:
                result['summary']['total'] += 1
                if parsed.get('healthy'):
                    result['summary']['healthy'] += 1
                if parsed.get('error'):
                    result['summary']['error'] += 1
                if parsed.get('busy'):
                    result['summary']['busy'] += 1
        
        return result
    
    def get_db_number(self) -> int:
        """获取 DB 块号"""
        return self.db_config['db_number']
    
    def get_total_size(self) -> int:
        """获取 DB 块总大小"""
        return self.db_config['total_size']
    
    def get_device_list(self) -> List[Dict]:
        """获取设备列表"""
        return [
            {
                'device_id': d.get('device_id', ''),
                'device_name': d.get('device_name', ''),
                'plc_name': d.get('plc_name', ''),
                'data_device_id': d.get('data_device_id', ''),
                'offset': d.get('start_offset', 0),
                'enabled': d.get('enabled', True)
            }
            for d in self.devices
        ]
    
    def get_health_summary(self, db30_data: bytes) -> Dict[str, Any]:
        """获取健康摘要 (简化版)
        
        Args:
            db30_data: DB30 完整字节数据
        
        Returns:
            健康摘要
        """
        parsed = self.parse_all(db30_data)
        summary = parsed['summary']
        
        # 整体健康状态判定
        overall_healthy = summary['error'] == 0
        
        # 找出异常设备
        error_devices = [
            {'device_id': k, 'device_name': v.get('device_name', ''), 'status_hex': v.get('status_hex', '')}
            for k, v in parsed['devices'].items()
            if v.get('error') and not v.get('skipped')
        ]
        
        return {
            'overall_healthy': overall_healthy,
            'total_devices': summary['total'],
            'healthy_count': summary['healthy'],
            'error_count': summary['error'],
            'busy_count': summary['busy'],
            'error_devices': error_devices,
            'timestamp': parsed['timestamp']
        }


# ============================================================
# 单例模式
# ============================================================
_parser_instance: Optional[ConfigDrivenDB30Parser] = None


def get_db30_parser() -> ConfigDrivenDB30Parser:
    """获取 DB30 解析器单例"""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = ConfigDrivenDB30Parser()
    return _parser_instance


# ============================================================
# 测试代码
# ============================================================
if __name__ == "__main__":
    parser = ConfigDrivenDB30Parser()
    
    # 模拟 DB30 数据 (40字节, 10个状态模块)
    test_data = bytes([
        # status_comm (offset 0): Done=true, 正常
        0x01, 0x00, 0x00, 0x00,
        # status_write_valve (offset 4): Busy=true, 正在写入
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
    
    print("\n📊 DB30 状态解析结果:")
    print(f"时间戳: {result['timestamp']}")
    print(f"DB块: {result['db_block']} ({result['db_name']})")
    
    print(f"\n📈 统计摘要:")
    print(f"  总设备数: {result['summary']['total']}")
    print(f"  正常: {result['summary']['healthy']}")
    print(f"  异常: {result['summary']['error']}")
    print(f"  忙碌: {result['summary']['busy']}")
    
    print("\n🔍 各设备状态:")
    for device_id, status in result['devices'].items():
        if status.get('skipped'):
            print(f"  ⏭️ {device_id}: 已跳过")
            continue
        
        health_icon = "✅" if status.get('healthy') else ("⚠️" if status.get('busy') else "❌")
        print(f"  {health_icon} {device_id}: {status.get('device_name', '')}")
        print(f"      Done={status.get('done')}, Busy={status.get('busy')}, "
              f"Error={status.get('error')}, Status={status.get('status_hex')}")
    
    print("\n🏥 健康摘要:")
    health = parser.get_health_summary(test_data)
    print(f"  整体健康: {'✅ 是' if health['overall_healthy'] else '❌ 否'}")
    print(f"  健康设备: {health['healthy_count']}/{health['total_devices']}")
    if health['error_devices']:
        print(f"  异常设备:")
        for dev in health['error_devices']:
            print(f"    - {dev['device_name']} ({dev['device_id']}): {dev['status_hex']}")
