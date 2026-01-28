"""
数据桥接器 - 连接后端 PLC 轮询和前端 UI

使用 Qt 信号槽机制实现线程间通信（零延迟）
"""
from PyQt6.QtCore import QObject, pyqtSignal
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class DataBridge(QObject):
    """数据桥接器（单例模式）
    
    功能：
    - 接收后端 PLC 轮询线程的数据
    - 通过 Qt 信号发送到前端 UI
    - 实现零延迟的线程间通信
    
    信号：
    - arc_data_updated: 弧流弧压数据更新（0.2s）
    - sensor_data_updated: 传感器数据更新（2s）
    - batch_status_changed: 批次状态变化
    - error_occurred: 错误信号
    """
    
    # Qt 信号定义
    arc_data_updated = pyqtSignal(dict)      # 弧流数据更新
    sensor_data_updated = pyqtSignal(dict)   # 传感器数据更新
    batch_status_changed = pyqtSignal(dict)  # 批次状态变化
    error_occurred = pyqtSignal(str)         # 错误信号
    connection_status_changed = pyqtSignal(bool)  # 连接状态变化
    
    _instance: Optional['DataBridge'] = None
    
    def __new__(cls):
        """单例模式：确保全局只有一个实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化数据桥接器"""
        if hasattr(self, '_initialized'):
            return
        
        super().__init__()
        self._initialized = True
        logger.info("✅ 数据桥接器已初始化")
    
    def emit_arc_data(self, data: Dict[str, Any]):
        """发送弧流数据到前端
        
        Args:
            data: 弧流弧压数据字典
                {
                    'arc_current': {'U': float, 'V': float, 'W': float},
                    'arc_voltage': {'U': float, 'V': float, 'W': float},
                    'setpoints': {'U': float, 'V': float, 'W': float},
                    'manual_deadzone_percent': float,
                    'timestamp': float
                }
        """
        try:
            self.arc_data_updated.emit(data)
        except Exception as e:
            logger.error(f"❌ 发送弧流数据失败: {e}")
            self.error_occurred.emit(f"发送弧流数据失败: {e}")
    
    def emit_sensor_data(self, data: Dict[str, Any]):
        """发送传感器数据到前端
        
        Args:
            data: 传感器数据字典
                {
                    'electrode_depths': {'1': float, '2': float, '3': float},
                    'cooling': {...},
                    'hopper': {...},
                    'valve_status': {...},
                    'valve_openness': {...},
                    'timestamp': float
                }
        """
        try:
            self.sensor_data_updated.emit(data)
        except Exception as e:
            logger.error(f"❌ 发送传感器数据失败: {e}")
            self.error_occurred.emit(f"发送传感器数据失败: {e}")
    
    def emit_batch_status(self, status: Dict[str, Any]):
        """发送批次状态到前端
        
        Args:
            status: 批次状态字典
                {
                    'is_smelting': bool,
                    'batch_code': str,
                    'start_time': float,
                    'elapsed_time': float
                }
        """
        try:
            self.batch_status_changed.emit(status)
        except Exception as e:
            logger.error(f"❌ 发送批次状态失败: {e}")
            self.error_occurred.emit(f"发送批次状态失败: {e}")
    
    def emit_error(self, error_msg: str):
        """发送错误信息到前端
        
        Args:
            error_msg: 错误消息
        """
        logger.error(f"❌ 错误: {error_msg}")
        self.error_occurred.emit(error_msg)
    
    def emit_connection_status(self, connected: bool):
        """发送连接状态到前端
        
        Args:
            connected: True=已连接, False=已断开
        """
        status = "已连接" if connected else "已断开"
        logger.info(f"🔗 PLC 连接状态: {status}")
        self.connection_status_changed.emit(connected)


# 全局单例访问函数
_data_bridge_instance: Optional[DataBridge] = None

def get_data_bridge() -> DataBridge:
    """获取数据桥接器单例
    
    Returns:
        DataBridge: 数据桥接器实例
    """
    global _data_bridge_instance
    if _data_bridge_instance is None:
        _data_bridge_instance = DataBridge()
    return _data_bridge_instance

