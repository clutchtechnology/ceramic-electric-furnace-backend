# ============================================================
# 文件说明: feeding_accumulator.py - 投料重量累计计算服务
# ============================================================
# 功能:
#   1. 维护60个数据点的队列（30秒历史，每0.5秒一个点）
#   2. 每30秒计算一次投料量
#   3. 根据 %Q3.7 (秤排料) 信号检测投料事件
#   4. 使用前3个点和后3个点的平均值计算投料量，防抖动
#   5. 从数据库查询累计值并更新
# ============================================================

import threading
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from collections import deque
from dataclasses import dataclass


@dataclass
class FeedingDataPoint:
    """单个数据点"""
    weight: float           # 料仓重量 (kg)
    is_discharging: bool    # %Q3.7 秤排料 (True=正在投料)
    is_requesting: bool     # %Q4.0 秤要料
    timestamp: datetime


class FeedingAccumulator:
    """投料重量累计计算器 - 单例模式
    
    投料检测逻辑:
    1. 每0.5秒读取一次料仓重量和投料信号
    2. 缓存60个数据点（30秒）
    3. 每30秒分析一次：找出所有 is_discharging=True 的连续段
    4. 每个连续段视为一次投料事件
    5. 投料量 = 开始3点平均重量 - 结束3点平均重量
    """
    
    _instance: Optional['FeedingAccumulator'] = None
    _lock = threading.Lock()
    
    # 队列大小: 60个点 (0.5s × 60 = 30秒)
    QUEUE_SIZE = 60
    # 计算间隔: 60次轮询 = 30秒
    CALC_INTERVAL = 60
    # 平均点数: 用于计算开始/结束重量
    AVG_POINTS = 3
    # 最小投料量阈值 (kg): 防止误检测
    MIN_FEEDING_KG = 1.0
    
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
        self._data_lock = threading.Lock()
        
        # ============================================================
        # 数据队列
        # ============================================================
        self._data_queue: deque = deque(maxlen=self.QUEUE_SIZE)
        
        # ============================================================
        # 累计状态
        # ============================================================
        self._feeding_total: float = 0.0      # 当前批次累计投料量 (kg)
        self._feeding_count: int = 0           # 投料次数
        self._current_batch_code: Optional[str] = None
        
        # ============================================================
        # 计数器
        # ============================================================
        self._poll_count: int = 0
        
        # ============================================================
        # 最近一次计算结果
        # ============================================================
        self._last_calc_result: Dict[str, Any] = {}
        
        print("✅ 投料累计器已初始化 (30秒窗口, 信号检测模式)")
    
    def reset_for_new_batch(self, batch_code: str):
        """重置累计量 (新批次开始时调用)
        
        逻辑:
        1. 先从数据库查询该批次的最新累计值
        2. 如果找到历史数据，则延续累计（续炼）
        3. 如果没有历史数据，则从0开始（新批次）
        """
        with self._data_lock:
            # 清空队列和计数器
            self._data_queue.clear()
            self._poll_count = 0
            self._last_calc_result = {}
            self._current_batch_code = batch_code
            
            # 尝试从数据库恢复历史累计值
            feeding_restored = self._restore_from_database(batch_code)
            
            if feeding_restored > 0:
                self._feeding_total = feeding_restored
                print(f"📥 投料累计已恢复 (批次: {batch_code}): {feeding_restored:.1f}kg")
            else:
                self._feeding_total = 0.0
                self._feeding_count = 0
                print(f"🆕 投料累计从0开始 (批次: {batch_code})")
    
    def _restore_from_database(self, batch_code: str) -> float:
        """从 InfluxDB 查询该批次的最新投料累计值
        
        Returns:
            feeding_total (kg)
        """
        try:
            from app.core.influxdb import get_influxdb_client
            from config import get_settings
            
            settings = get_settings()
            influx = get_influxdb_client()
            
            query = f'''
                from(bucket: "{settings.influxdb_bucket}")
                    |> range(start: -7d)
                    |> filter(fn: (r) => r["_measurement"] == "sensor_data")
                    |> filter(fn: (r) => r["batch_code"] == "{batch_code}")
                    |> filter(fn: (r) => r["module_type"] == "hopper_weight")
                    |> filter(fn: (r) => r["_field"] == "feeding_total")
                    |> last()
            '''
            
            result = influx.query_api().query(query)
            
            feeding_total = 0.0
            
            for table in result:
                for record in table.records:
                    value = record.get_value()
                    feeding_total = float(value) if value else 0.0
                    break
            
            return feeding_total
            
        except Exception as e:
            print(f"⚠️ 从数据库恢复投料累计失败: {e}")
            return 0.0
    
    def add_measurement(
        self,
        weight_kg: float,
        is_discharging: bool,
        is_requesting: bool = False
    ) -> Dict[str, Any]:
        """添加一次测量数据
        
        Args:
            weight_kg: 料仓当前重量 (kg)
            is_discharging: %Q3.7 秤排料信号 (True=正在投料)
            is_requesting: %Q4.0 秤要料信号
            
        Returns:
            {
                'should_calc': bool,          # 是否需要计算投料
                'queue_size': int,            # 当前队列大小
                'feeding_total': float,       # 当前累计投料量
            }
        """
        with self._data_lock:
            # 1. 添加到队列
            point = FeedingDataPoint(
                weight=weight_kg,
                is_discharging=is_discharging,
                is_requesting=is_requesting,
                timestamp=datetime.now(timezone.utc)
            )
            self._data_queue.append(point)
            
            # 2. 计数器递增
            self._poll_count += 1
            
            # 3. 检查是否需要计算 (每60次 = 30秒)
            should_calc = self._poll_count >= self.CALC_INTERVAL
            
            return {
                'should_calc': should_calc,
                'queue_size': len(self._data_queue),
                'feeding_total': self._feeding_total,
                'is_discharging': is_discharging,
            }
    
    def calculate_feeding(self) -> Dict[str, Any]:
        """分析队列数据，计算投料量
        
        逻辑:
        1. 找出所有 is_discharging=True 的连续段
        2. 每个连续段视为一次投料事件
        3. 投料量 = 开始3点平均 - 结束3点平均
        4. 累加到 feeding_total
        
        Returns:
            {
                'feeding_events': List[Dict],  # 检测到的投料事件列表
                'total_added': float,          # 本次新增投料量
                'feeding_total': float,        # 累计投料量
                'feeding_count': int,          # 累计投料次数
            }
        """
        with self._data_lock:
            # 重置计数器
            self._poll_count = 0
            
            if len(self._data_queue) < 10:
                return {
                    'feeding_events': [],
                    'total_added': 0.0,
                    'feeding_total': self._feeding_total,
                    'feeding_count': self._feeding_count,
                    'message': '队列数据不足'
                }
            
            # 转换为列表便于索引
            data_list = list(self._data_queue)
            feeding_events = []
            
            # 查找连续的 is_discharging=True 段
            i = 0
            while i < len(data_list):
                if data_list[i].is_discharging:
                    # 找到投料开始
                    start_idx = i
                    
                    # 找到投料结束
                    while i < len(data_list) and data_list[i].is_discharging:
                        i += 1
                    end_idx = i - 1
                    
                    # 需要至少2个连续点才算有效投料
                    if end_idx - start_idx >= 1:
                        # 计算开始重量 (前3个点平均)
                        start_points = min(self.AVG_POINTS, end_idx - start_idx + 1)
                        start_weights = [data_list[j].weight for j in range(start_idx, start_idx + start_points)]
                        start_avg = sum(start_weights) / len(start_weights)
                        
                        # 计算结束重量 (后3个点平均)
                        end_points = min(self.AVG_POINTS, end_idx - start_idx + 1)
                        end_weights = [data_list[j].weight for j in range(end_idx - end_points + 1, end_idx + 1)]
                        end_avg = sum(end_weights) / len(end_weights)
                        
                        # 投料量
                        feeding_amount = start_avg - end_avg
                        
                        # 只记录有效投料 (重量减少且超过阈值)
                        if feeding_amount >= self.MIN_FEEDING_KG:
                            event = {
                                'start_idx': start_idx,
                                'end_idx': end_idx,
                                'duration_points': end_idx - start_idx + 1,
                                'start_weight': start_avg,
                                'end_weight': end_avg,
                                'amount': feeding_amount,
                                'start_time': data_list[start_idx].timestamp.isoformat(),
                                'end_time': data_list[end_idx].timestamp.isoformat(),
                            }
                            feeding_events.append(event)
                else:
                    i += 1
            
            # 累加投料量
            total_added = sum(e['amount'] for e in feeding_events)
            self._feeding_total += total_added
            self._feeding_count += len(feeding_events)
            
            result = {
                'feeding_events': feeding_events,
                'total_added': total_added,
                'feeding_total': self._feeding_total,
                'feeding_count': self._feeding_count,
                'queue_analyzed': len(data_list),
            }
            
            self._last_calc_result = result
            
            # 打印日志
            if feeding_events:
                print(f"📦 检测到 {len(feeding_events)} 次投料:")
                for idx, e in enumerate(feeding_events):
                    print(f"   第{idx+1}次: {e['start_weight']:.1f}kg → {e['end_weight']:.1f}kg = {e['amount']:.1f}kg")
                print(f"   本次新增: {total_added:.1f}kg, 累计: {self._feeding_total:.1f}kg")
            
            return result
    
    def get_feeding_total(self) -> float:
        """获取累计投料量 (kg)"""
        with self._data_lock:
            return self._feeding_total
    
    def get_realtime_data(self) -> Dict[str, Any]:
        """获取实时数据 (供API调用)"""
        with self._data_lock:
            current_weight = self._data_queue[-1].weight if self._data_queue else 0.0
            is_discharging = self._data_queue[-1].is_discharging if self._data_queue else False
            
            return {
                'feeding_total': self._feeding_total,
                'feeding_count': self._feeding_count,
                'current_weight': current_weight,
                'is_discharging': is_discharging,
                'batch_code': self._current_batch_code,
                'queue_size': len(self._data_queue),
                'last_calc_result': self._last_calc_result,
            }
    
    def set_feeding_total(self, total: float):
        """设置累计投料量 (从数据库恢复时使用)"""
        with self._data_lock:
            self._feeding_total = total
            print(f"📥 投料累计已从数据库恢复: {total:.1f}kg")


# ============================================================
# 全局单例获取函数
# ============================================================

_feeding_accumulator: Optional[FeedingAccumulator] = None

def get_feeding_accumulator() -> FeedingAccumulator:
    """获取投料累计器单例"""
    global _feeding_accumulator
    if _feeding_accumulator is None:
        _feeding_accumulator = FeedingAccumulator()
    return _feeding_accumulator
