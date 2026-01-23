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
        self._port: int = settings.plc_port  # 端口 (默认102, Docker环境用10102)
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
        
        # 仅在 DEBUG 模式下打印初始化信息
        if settings.debug:
            print(f"📡 PLC Manager 初始化: {self._ip}:{self._port} (rack={self._rack}, slot={self._slot})")
    
    def connect(self) -> Tuple[bool, str]:
        """连接到 PLC"""
        with self._rw_lock:
            return self._connect_internal()
    
    def _connect_internal(self) -> Tuple[bool, str]:
        """内部连接方法 (不加锁，供已持有锁的方法调用)"""
        if self._connected and self._client:
            return (True, "已连接")
        
        if not SNAP7_AVAILABLE:
            return (False, "snap7 未安装")
        
        try:
            self._client = snap7.client.Client()
            # python-snap7 2.0+ 不再支持 tcpport 参数，使用标准端口 102
            self._client.connect(self._ip, self._rack, self._slot)
            self._connected = True
            self._last_connect_time = datetime.now()
            self._connect_count += 1
            self._consecutive_error_count = 0
            print(f"✅ PLC 连接成功: {self._ip}:{self._port}")
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
            self._disconnect_internal()
    
    def _disconnect_internal(self):
        """内部断开方法 (不加锁，供已持有锁的方法调用)"""
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
                # 尝试重连 (使用内部方法，避免死锁)
                success, msg = self._connect_internal()
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
                    self._disconnect_internal()
                
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
                # 使用内部方法避免死锁 (已持有 _rw_lock)
                success, msg = self._connect_internal()
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
    
    def read_output_area(self, start: int, size: int) -> Tuple[Optional[bytes], str]:
        """读取 PLC 输出区域 (Q 区)
        
        Args:
            start: 起始字节偏移量 (例如 %Q3.x 则 start=3)
            size: 读取字节数
            
        Returns:
            (数据, 错误信息)
            
        示例:
            读取 %Q3.7 和 %Q4.0:
            data, err = plc.read_output_area(3, 2)  # 读取2字节 (Q3和Q4)
            q3_7 = (data[0] >> 7) & 0x01  # Q3.7
            q4_0 = data[1] & 0x01          # Q4.0
        """
        with self._rw_lock:
            if not self._connected or not self._client:
                success, msg = self._connect_internal()
                if not success:
                    return (None, msg)
            
            try:
                # snap7 area codes: 0x82 = Output (Q)
                # Areas.PA = 0x82 (Process Outputs)
                data = self._client.read_area(snap7.types.Areas.PA, 0, start, size)
                self._last_read_time = datetime.now()
                self._consecutive_error_count = 0
                return (bytes(data), "")
            except Exception as e:
                self._error_count += 1
                self._consecutive_error_count += 1
                self._last_error = str(e)
                return (None, str(e))

    def get_status(self) -> Dict[str, Any]:
        """获取连接状态信息"""
        return {
            'connected': self._connected,
            'ip': self._ip,
            'port': self._port,
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
    
    def health_check(self) -> Tuple[bool, str]:
        """健康检查（尝试读取少量数据）
        
        Returns:
            (healthy, message)
        """
        # 尝试读取 DB32 的前 4 字节
        data, err = self.read_db(32, 0, 4)
        if data:
            return (True, "PLC 响应正常")
        return (False, err)
    
    def update_config(self, ip: str = None, rack: int = None, slot: int = None):
        """更新 PLC 连接配置（需要重连生效）"""
        with self._rw_lock:
            if ip:
                self._ip = ip
            if rack is not None:
                self._rack = rack
            if slot is not None:
                self._slot = slot
            
            # 断开旧连接
            if self._client:
                try:
                    if SNAP7_AVAILABLE and self._client.get_connected():
                        self._client.disconnect()
                except:
                    pass
            self._connected = False
            print(f"📡 PLC 配置已更新: {self._ip}:{self._rack}/{self._slot}")


# 全局单例获取函数
_plc_manager: Optional[PLCManager] = None

def get_plc_manager() -> PLCManager:
    """获取 PLC 管理器单例"""
    global _plc_manager
    if _plc_manager is None:
        _plc_manager = PLCManager()
    return _plc_manager


def reset_plc_manager() -> None:
    """重置 PLC 管理器（用于配置更新后）"""
    global _plc_manager
    if _plc_manager is not None:
        _plc_manager.disconnect()
        _plc_manager = None
