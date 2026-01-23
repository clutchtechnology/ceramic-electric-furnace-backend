# PLC通信模块

from .plc_manager import PLCManager, get_plc_manager, reset_plc_manager, SNAP7_AVAILABLE
from .parser_modbus import ModbusDataParser
from .parser_status import ModbusStatusParser
from .parser_config_db32 import ConfigDrivenDB32Parser, get_db32_parser
from .parser_status_db30 import ConfigDrivenDB30Parser, get_db30_parser

__all__ = [
    # PLC 连接管理
    'PLCManager',
    'get_plc_manager',
    'reset_plc_manager',
    'SNAP7_AVAILABLE',
    # 旧解析器 (兼容)
    'ModbusDataParser',
    'ModbusStatusParser',
    # 配置驱动解析器
    'ConfigDrivenDB32Parser',
    'ConfigDrivenDB30Parser',
    'get_db32_parser',
    'get_db30_parser',
]
