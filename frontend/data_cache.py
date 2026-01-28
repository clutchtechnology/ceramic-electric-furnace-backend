"""
内存缓存管理器 - 统一管理实时数据缓存

功能：
- 存储最新的弧流、传感器数据
- 存储最近 N 条历史数据（用于图表）
- 提供线程安全的读写接口
- 无需 Redis，使用 Python 内存缓存

使用场景：
- PLC 轮询线程写入数据
- GUI 线程读取数据
- 历史曲线图表查询最近数据
"""
from typing import Dict, Any, List, Optional
from collections import deque
from threading import Lock
import time
import logging

logger = logging.getLogger(__name__)


class DataCache:
    """数据缓存管理器（单例模式）
    
    特点：
    - 线程安全：使用 Lock 保护数据
    - 内存高效：使用 deque 自动限制大小
    - 性能优秀：内存读写，微秒级延迟
    """
    
    _instance: Optional['DataCache'] = None
    _lock = Lock()
    
    def __new__(cls):
        """单例模式：确保全局只有一个实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化缓存管理器"""
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        
        # 最新数据（单条）
        self._latest_arc_data: Dict[str, Any] = {}
        self._latest_sensor_data: Dict[str, Any] = {}
        self._latest_batch_status: Dict[str, Any] = {}
        
        # 历史数据（用于图表，保留最近 1000 条）
        self._arc_history: deque = deque(maxlen=1000)
        self._sensor_history: deque = deque(maxlen=1000)
        
        # 读写锁（细粒度锁，提高并发性能）
        self._arc_lock = Lock()
        self._sensor_lock = Lock()
        self._batch_lock = Lock()
        
        logger.info("✅ 数据缓存管理器已初始化")
        logger.info(f"   - 弧流历史缓存: {self._arc_history.maxlen} 条")
        logger.info(f"   - 传感器历史缓存: {self._sensor_history.maxlen} 条")
    
    # ========== 弧流数据 ==========
    
    def set_arc_data(self, data: Dict[str, Any]):
        """存储弧流数据（线程安全）
        
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
        with self._arc_lock:
            self._latest_arc_data = data.copy()
            self._arc_history.append({
                'data': data.copy(),
                'timestamp': time.time()
            })
    
    def get_arc_data(self) -> Dict[str, Any]:
        """获取最新弧流数据（线程安全）
        
        Returns:
            最新弧流数据字典
        """
        with self._arc_lock:
            return self._latest_arc_data.copy()
    
    def get_arc_history(self, count: int = 100) -> List[Dict[str, Any]]:
        """获取弧流历史数据（线程安全）
        
        Args:
            count: 获取最近 N 条数据
        
        Returns:
            历史数据列表
        """
        with self._arc_lock:
            return list(self._arc_history)[-count:]
    
    # ========== 传感器数据 ==========
    
    def set_sensor_data(self, data: Dict[str, Any]):
        """存储传感器数据（线程安全）
        
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
        with self._sensor_lock:
            self._latest_sensor_data = data.copy()
            self._sensor_history.append({
                'data': data.copy(),
                'timestamp': time.time()
            })
    
    def get_sensor_data(self) -> Dict[str, Any]:
        """获取最新传感器数据（线程安全）
        
        Returns:
            最新传感器数据字典
        """
        with self._sensor_lock:
            return self._latest_sensor_data.copy()
    
    def get_sensor_history(self, count: int = 100) -> List[Dict[str, Any]]:
        """获取传感器历史数据（线程安全）
        
        Args:
            count: 获取最近 N 条数据
        
        Returns:
            历史数据列表
        """
        with self._sensor_lock:
            return list(self._sensor_history)[-count:]
    
    # ========== 批次状态 ==========
    
    def set_batch_status(self, status: Dict[str, Any]):
        """存储批次状态（线程安全）
        
        Args:
            status: 批次状态字典
                {
                    'is_smelting': bool,
                    'batch_code': str,
                    'start_time': float,
                    'elapsed_time': float
                }
        """
        with self._batch_lock:
            self._latest_batch_status = status.copy()
    
    def get_batch_status(self) -> Dict[str, Any]:
        """获取批次状态（线程安全）
        
        Returns:
            批次状态字典
        """
        with self._batch_lock:
            return self._latest_batch_status.copy()
    
    # ========== 统计信息 ==========
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息
        
        Returns:
            统计信息字典
        """
        return {
            'arc_history_count': len(self._arc_history),
            'sensor_history_count': len(self._sensor_history),
            'has_arc_data': bool(self._latest_arc_data),
            'has_sensor_data': bool(self._latest_sensor_data),
            'has_batch_status': bool(self._latest_batch_status),
            'arc_history_maxlen': self._arc_history.maxlen,
            'sensor_history_maxlen': self._sensor_history.maxlen
        }
    
    def clear(self):
        """清空所有缓存（线程安全）"""
        with self._arc_lock, self._sensor_lock, self._batch_lock:
            self._latest_arc_data.clear()
            self._latest_sensor_data.clear()
            self._latest_batch_status.clear()
            self._arc_history.clear()
            self._sensor_history.clear()
        logger.info("🗑️ 缓存已清空")


# 全局单例访问函数
_data_cache_instance: Optional[DataCache] = None

def get_data_cache() -> DataCache:
    """获取数据缓存管理器单例
    
    Returns:
        DataCache: 数据缓存管理器实例
    """
    global _data_cache_instance
    if _data_cache_instance is None:
        _data_cache_instance = DataCache()
    return _data_cache_instance

