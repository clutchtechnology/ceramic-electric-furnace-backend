# ============================================================
# 文件说明: plc_manager.py - PLC 长连接管理器
# ============================================================
# 功能:
#   1. 维护 PLC 长连接（避免频繁连接/断开）
#   2. 自动重连机制
#   3. 连接健康检查
#   4. 线程安全读写
# ============================================================

import threading
import time
from typing import Optional, Tuple, Dict, Any
from datetime import datetime

from config import get_settings

settings = get_settings()

# 尝试导入 snap7
try:
    import snap7
    from snap7.util import get_real, get_int
    SNAP7_AVAILABLE = True
except ImportError:
    SNAP7_AVAILABLE = False
    print("⚠️ snap7 未安装，使用模拟模式")


class PLCManager:
    """PLC 长连接管理器（单例模式）"""
    
    _instance: Optional['PLCManager'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        
        # 连接配置
        self._ip: str = settings.plc_ip
        self._rack: int = settings.plc_rack
        self._slot: int = settings.plc_slot
        
        # 连接状态
        self._client: Optional['snap7.client.Client'] = None
        self._connected: bool = False
        self._last_connect_time: Optional[datetime] = None
        self._last_read_time: Optional[datetime] = None
        self._connect_count: int = 0
        self._error_count: int = 0
        self._consecutive_error_count: int = 0
        self._last_error: str = ""
        
        # 线程锁
        self._rw_lock = threading.Lock()
        
        # 重连配置
        self._reconnect_interval: float = 5.0
        self._max_reconnect_attempts: int = 3
        self._max_consecutive_errors: int = 10
        
        print(f"📡 PLC Manager 初始化: {self._ip}:{self._rack}/{self._slot}")
    
    def connect(self) -> Tuple[bool, str]:
        """连接到 PLC"""
        with self._rw_lock:
            if self._connected and self._client:
                return (True, "已连接")
            
            if not SNAP7_AVAILABLE:
                return (False, "snap7 未安装")
            
            try:
                self._client = snap7.client.Client()
                self._client.connect(self._ip, self._rack, self._slot)
                self._connected = True
                self._last_connect_time = datetime.now()
                self._connect_count += 1
                self._consecutive_error_count = 0
                print(f"✅ PLC 连接成功: {self._ip}")
                return (True, "连接成功")
            except Exception as e:
                self._connected = False
                self._last_error = str(e)
                self._error_count += 1
                print(f"❌ PLC 连接失败: {e}")
                return (False, str(e))
    
    def disconnect(self):
        """断开 PLC 连接"""
        with self._rw_lock:
            if self._client:
                try:
                    self._client.disconnect()
                except:
                    pass
                self._client = None
            self._connected = False
            print("📡 PLC 连接已断开")
    
    def read_db(self, db_number: int, start: int, size: int) -> Tuple[Optional[bytes], str]:
        """读取 DB 块数据
        
        Args:
            db_number: DB 块号
            start: 起始偏移量
            size: 读取字节数
            
        Returns:
            (数据, 错误信息)
        """
        with self._rw_lock:
            if not self._connected or not self._client:
                # 尝试重连
                success, msg = self.connect()
                if not success:
                    return (None, msg)
            
            try:
                data = self._client.db_read(db_number, start, size)
                self._last_read_time = datetime.now()
                self._consecutive_error_count = 0
                return (bytes(data), "")
            except Exception as e:
                self._error_count += 1
                self._consecutive_error_count += 1
                self._last_error = str(e)
                
                # 连续错误过多，强制重连
                if self._consecutive_error_count >= self._max_consecutive_errors:
                    print(f"⚠️ 连续 {self._consecutive_error_count} 次错误，强制重连")
                    self.disconnect()
                
                return (None, str(e))
    
    def write_db(self, db_number: int, start: int, data: bytes) -> Tuple[bool, str]:
        """写入 DB 块数据
        
        Args:
            db_number: DB 块号
            start: 起始偏移量
            data: 要写入的数据
            
        Returns:
            (成功, 错误信息)
        """
        with self._rw_lock:
            if not self._connected or not self._client:
                success, msg = self.connect()
                if not success:
                    return (False, msg)
            
            try:
                self._client.db_write(db_number, start, data)
                self._consecutive_error_count = 0
                return (True, "")
            except Exception as e:
                self._error_count += 1
                self._consecutive_error_count += 1
                self._last_error = str(e)
                return (False, str(e))
    
    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._connected and self._client is not None
    
    def get_status(self) -> Dict[str, Any]:
        """获取连接状态信息"""
        return {
            'connected': self._connected,
            'ip': self._ip,
            'rack': self._rack,
            'slot': self._slot,
            'connect_count': self._connect_count,
            'error_count': self._error_count,
            'consecutive_errors': self._consecutive_error_count,
            'last_error': self._last_error,
            'last_connect_time': self._last_connect_time.isoformat() if self._last_connect_time else None,
            'last_read_time': self._last_read_time.isoformat() if self._last_read_time else None,
            'snap7_available': SNAP7_AVAILABLE
        }


# 全局单例获取函数
_plc_manager: Optional[PLCManager] = None

def get_plc_manager() -> PLCManager:
    """获取 PLC 管理器单例"""
    global _plc_manager
    if _plc_manager is None:
        _plc_manager = PLCManager()
    return _plc_manager
