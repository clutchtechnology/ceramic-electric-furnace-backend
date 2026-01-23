# ============================================================
# 文件说明: valve_calculator_service.py - 蝶阀开度计算服务
# ============================================================
# 功能:
#   1. 维护35秒滑动窗口队列 (高频轮询约0.5秒/次 → 约70个数据点)
#   2. 增量计算蝶阀开度百分比
#   3. 自动校准: 连续30秒的10(关)或01(开)触发校准
#   4. 批次重置: 新批次开度归零
# ============================================================
# 状态编码:
#   - "01": 正在开启
#   - "10": 正在关闭
#   - "00": 停止 (不动作)
#   - "11": 异常/故障
# ============================================================

import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from collections import deque
from dataclasses import dataclass, field

from app.services.valve_config_service import get_valve_config_service


# ============================================================
# 配置常量
# ============================================================
WINDOW_DURATION_SECONDS = 35.0   # 滑动窗口时长: 35秒
POLLING_INTERVAL = 0.5          # 轮询间隔: 0.5秒 (DB32高频轮询)
MAX_QUEUE_SIZE = 100            # 队列最大长度 (35s / 0.5s = 70, 留余量)
CALIBRATION_THRESHOLD = 30.0    # 校准触发阈值: 连续30秒


@dataclass
class ValveStateRecord:
    """蝶阀状态记录"""
    status: str              # "01", "10", "00", "11"
    timestamp: datetime      # 记录时间
    interval: float = 0.0    # 与上一条记录的时间间隔(秒)


@dataclass
class ValveOpenness:
    """蝶阀开度状态"""
    valve_id: int
    openness_percent: float = 0.0      # 当前开度 (0-100%)
    current_status: str = "00"         # 当前状态
    last_calibration: Optional[str] = None  # 上次校准 ("full_open" / "full_close")
    calibration_time: Optional[datetime] = None
    batch_code: Optional[str] = None   # 所属批次号
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "valve_id": self.valve_id,
            "openness_percent": round(self.openness_percent, 2),
            "current_status": self.current_status,
            "last_calibration": self.last_calibration,
            "calibration_time": self.calibration_time.isoformat() if self.calibration_time else None,
            "batch_code": self.batch_code
        }


class ValveCalculatorService:
    """蝶阀开度计算服务 (单例模式)"""
    
    _instance: Optional['ValveCalculatorService'] = None
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
        
        # 4组蝶阀的状态队列 (滑动窗口)
        self._status_queues: Dict[int, deque] = {
            1: deque(maxlen=MAX_QUEUE_SIZE),
            2: deque(maxlen=MAX_QUEUE_SIZE),
            3: deque(maxlen=MAX_QUEUE_SIZE),
            4: deque(maxlen=MAX_QUEUE_SIZE),
        }
        
        # 4组蝶阀的开度状态
        self._openness: Dict[int, ValveOpenness] = {
            i: ValveOpenness(valve_id=i) for i in range(1, 5)
        }
        
        # 上一次记录时间 (用于计算时间间隔)
        self._last_record_time: Dict[int, Optional[datetime]] = {
            i: None for i in range(1, 5)
        }
        
        # 当前批次号
        self._current_batch_code: Optional[str] = None
        
        # 数据锁
        self._data_lock = threading.Lock()
        
        self._initialized = True
        print("✅ 蝶阀开度计算服务已初始化")
    
    def add_status(self, valve_id: int, status: str, timestamp: Optional[datetime] = None):
        """添加蝶阀状态记录
        
        Args:
            valve_id: 蝶阀编号 (1-4)
            status: 状态码 ("01", "10", "00", "11")
            timestamp: 记录时间 (默认当前时间)
        """
        if valve_id < 1 or valve_id > 4:
            return
        
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        with self._data_lock:
            # 计算时间间隔
            last_time = self._last_record_time[valve_id]
            if last_time:
                interval = (timestamp - last_time).total_seconds()
            else:
                interval = POLLING_INTERVAL  # 首次记录使用默认间隔
            
            # 创建记录
            record = ValveStateRecord(
                status=status,
                timestamp=timestamp,
                interval=interval
            )
            
            # 添加到队列
            self._status_queues[valve_id].append(record)
            self._last_record_time[valve_id] = timestamp
            
            # 更新当前状态
            self._openness[valve_id].current_status = status
            
            # 计算开度变化
            self._calculate_openness_delta(valve_id, status, interval)
            
            # 清理过期记录 (超过35秒的)
            self._cleanup_old_records(valve_id, timestamp)
            
            # 检查是否需要校准
            self._check_calibration(valve_id)
    
    def _calculate_openness_delta(self, valve_id: int, status: str, interval: float):
        """计算开度增量
        
        Args:
            valve_id: 蝶阀编号
            status: 当前状态
            interval: 时间间隔(秒)
        """
        config_service = get_valve_config_service()
        config = config_service.get_config(valve_id)
        
        openness = self._openness[valve_id]
        
        if status == "01":  # 正在开启
            # 开度增加: interval / 全开时间 * 100%
            delta = (interval / config.full_open_time) * 100.0
            openness.openness_percent = min(100.0, openness.openness_percent + delta)
            
        elif status == "10":  # 正在关闭
            # 开度减少: interval / 全关时间 * 100%
            delta = (interval / config.full_close_time) * 100.0
            openness.openness_percent = max(0.0, openness.openness_percent - delta)
        
        # "00"(停止) 和 "11"(故障) 不改变开度
    
    def _cleanup_old_records(self, valve_id: int, current_time: datetime):
        """清理超过35秒的旧记录"""
        queue = self._status_queues[valve_id]
        cutoff_time = current_time - timedelta(seconds=WINDOW_DURATION_SECONDS)
        
        while queue and queue[0].timestamp < cutoff_time:
            queue.popleft()
    
    def _check_calibration(self, valve_id: int):
        """检查是否需要校准 (连续30秒相同状态)
        
        如果滑动窗口中连续30秒都是:
        - "10" (关闭中): 触发全关校准, 开度设为0%
        - "01" (开启中): 触发全开校准, 开度设为100%
        """
        queue = self._status_queues[valve_id]
        if not queue:
            return
        
        # 检查最近30秒的状态是否全部一致
        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(seconds=CALIBRATION_THRESHOLD)
        
        # 收集30秒内的所有记录
        recent_records = [r for r in queue if r.timestamp >= cutoff_time]
        
        if not recent_records:
            return
        
        # 计算30秒内的有效时间
        total_time = sum(r.interval for r in recent_records)
        if total_time < CALIBRATION_THRESHOLD * 0.9:  # 至少27秒的数据
            return
        
        # 检查是否全部是同一状态
        statuses = set(r.status for r in recent_records)
        
        if len(statuses) == 1:
            status = statuses.pop()
            openness = self._openness[valve_id]
            
            if status == "10":  # 连续30秒关闭 → 全关校准
                if openness.last_calibration != "full_close":
                    openness.openness_percent = 0.0
                    openness.last_calibration = "full_close"
                    openness.calibration_time = now
                    print(f"🔧 蝶阀{valve_id}触发全关校准: 开度重置为0%")
                    
            elif status == "01":  # 连续30秒开启 → 全开校准
                if openness.last_calibration != "full_open":
                    openness.openness_percent = 100.0
                    openness.last_calibration = "full_open"
                    openness.calibration_time = now
                    print(f"🔧 蝶阀{valve_id}触发全开校准: 开度重置为100%")
    
    def reset_openness(self, valve_id: Optional[int] = None, batch_code: Optional[str] = None):
        """重置蝶阀开度
        
        Args:
            valve_id: 指定蝶阀编号, None表示重置所有
            batch_code: 新批次号
        """
        with self._data_lock:
            if valve_id is not None:
                # 重置单个蝶阀
                if valve_id in self._openness:
                    self._openness[valve_id].openness_percent = 0.0
                    self._openness[valve_id].last_calibration = None
                    self._openness[valve_id].calibration_time = None
                    self._openness[valve_id].batch_code = batch_code
                    self._status_queues[valve_id].clear()
                    self._last_record_time[valve_id] = None
                    print(f"🔄 蝶阀{valve_id}开度已重置为0%")
            else:
                # 重置所有蝶阀
                for vid in range(1, 5):
                    self._openness[vid].openness_percent = 0.0
                    self._openness[vid].last_calibration = None
                    self._openness[vid].calibration_time = None
                    self._openness[vid].batch_code = batch_code
                    self._status_queues[vid].clear()
                    self._last_record_time[vid] = None
                print(f"🔄 所有蝶阀开度已重置为0% (批次: {batch_code})")
            
            self._current_batch_code = batch_code
    
    def set_batch_code(self, batch_code: str):
        """设置当前批次号"""
        with self._data_lock:
            self._current_batch_code = batch_code
            for vid in range(1, 5):
                self._openness[vid].batch_code = batch_code
    
    def get_openness(self, valve_id: int) -> ValveOpenness:
        """获取单个蝶阀开度"""
        with self._data_lock:
            return self._openness.get(valve_id, ValveOpenness(valve_id=valve_id))
    
    def get_all_openness(self) -> Dict[int, ValveOpenness]:
        """获取所有蝶阀开度"""
        with self._data_lock:
            return {vid: openness for vid, openness in self._openness.items()}
    
    def get_queue_status(self, valve_id: int) -> Dict[str, Any]:
        """获取队列状态 (调试用)"""
        with self._data_lock:
            queue = self._status_queues.get(valve_id, deque())
            return {
                "valve_id": valve_id,
                "queue_length": len(queue),
                "window_duration": WINDOW_DURATION_SECONDS,
                "records": [
                    {
                        "status": r.status,
                        "timestamp": r.timestamp.isoformat(),
                        "interval": r.interval
                    }
                    for r in queue
                ][-20:]  # 只返回最近20条
            }
    
    def batch_add_statuses(self, valve_byte: int, timestamp: Optional[datetime] = None):
        """批量添加4个蝶阀的状态 (从原始字节解析)
        
        Args:
            valve_byte: 蝶阀状态字节 (1 byte = 8 bits, 每2bit对应一个蝶阀)
            timestamp: 记录时间
        
        字节结构:
            bit 0-1: 蝶阀1 (bit0=关闭信号, bit1=开启信号)
            bit 2-3: 蝶阀2
            bit 4-5: 蝶阀3
            bit 6-7: 蝶阀4
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        for valve_id in range(1, 5):
            bit_offset = (valve_id - 1) * 2
            bit_close = (valve_byte >> bit_offset) & 0x01
            bit_open = (valve_byte >> (bit_offset + 1)) & 0x01
            
            # 组合状态: "关开" 格式
            status = f"{bit_close}{bit_open}"
            
            self.add_status(valve_id, status, timestamp)


# ============================================================
# 便捷函数
# ============================================================
def get_valve_calculator_service() -> ValveCalculatorService:
    """获取蝶阀开度计算服务实例"""
    return ValveCalculatorService()


def add_valve_status(valve_id: int, status: str, timestamp: Optional[datetime] = None):
    """添加蝶阀状态 (便捷函数)"""
    service = get_valve_calculator_service()
    service.add_status(valve_id, status, timestamp)


def batch_add_valve_statuses(valve_byte: int, timestamp: Optional[datetime] = None):
    """批量添加蝶阀状态 (便捷函数)"""
    service = get_valve_calculator_service()
    service.batch_add_statuses(valve_byte, timestamp)


def get_all_valve_openness() -> Dict[str, Any]:
    """获取所有蝶阀开度 (便捷函数)"""
    service = get_valve_calculator_service()
    openness_map = service.get_all_openness()
    return {
        str(vid): openness.to_dict()
        for vid, openness in openness_map.items()
    }


def reset_all_valve_openness(batch_code: Optional[str] = None):
    """重置所有蝶阀开度 (便捷函数)"""
    service = get_valve_calculator_service()
    service.reset_openness(batch_code=batch_code)
