# ============================================================
# 文件说明: feeding_calculator.py - 智能投料量计算服务
# ============================================================
# 算法原理:
#   1. 维护60条重量历史数据（30秒，0.5秒/次）
#   2. 每15秒分析一次滑动窗口（30条数据）
#   3. 检测加料过程（重量上升 + 要料信号 = 1）
#   4. 投料量 = (起始重量 - 结束重量) + 加料量
#   5. 使用卡尔曼滤波抗±5kg抖动
# ============================================================
# 核心逻辑:
#   - 要料信号(%Q4.0)=1 → 正在加料（重量上升）
#   - 排料信号(%Q3.7)=1 → 正在投料（重量下降）
#   - 队列示例: [3, 2, 1, 2, 3, 4, 5, 4, 3, 3, 3]
#     要料信号在 1→5 时为1，加料量 = 5-1 = 4kg
#     净投料 = (3-3) + 4 = 4kg
# ============================================================

from collections import deque
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import threading

from app.tools.kalman_filter import AdaptiveKalmanFilter, create_weight_filter


@dataclass
class WeightRecord:
    """重量记录"""
    timestamp: datetime
    raw_weight: float          # 原始重量 (kg)
    filtered_weight: float     # 滤波后重量 (kg)
    is_discharging: bool       # 排料信号 (%Q3.7)
    is_requesting: bool        # 要料信号 (%Q4.0)
    

@dataclass
class FeedingSegment:
    """加料段识别结果"""
    start_idx: int             # 起始索引
    end_idx: int               # 结束索引
    min_weight: float          # 最低点重量
    max_weight: float          # 最高点重量
    feeding_amount: float      # 加料量 (kg)
    timestamp: datetime        # 加料开始时间


class FeedingCalculator:
    """智能投料量计算器"""
    
    def __init__(self, queue_size: int = 60, window_size: int = 30):
        """初始化
        
        Args:
            queue_size: 队列大小（默认60条 = 30秒历史）
            window_size: 滑动窗口大小（默认30条 = 15秒）
        """
        self.queue_size = queue_size
        self.window_size = window_size
        
        # 重量队列
        self._weight_queue: deque[WeightRecord] = deque(maxlen=queue_size)
        self._lock = threading.Lock()
        
        # 卡尔曼滤波器
        self._kalman_filter: Optional[AdaptiveKalmanFilter] = None
        
        # 投料状态
        self._last_feeding_weight: Optional[float] = None  # 上次投料后的重量
        self._initial_weight: Optional[float] = None       # 批次初始重量
        self._batch_code: Optional[str] = None
        
    def initialize_batch(self, batch_code: str, initial_weight: float):
        """初始化新批次
        
        Args:
            batch_code: 批次编号
            initial_weight: 初始重量 (kg)
        """
        with self._lock:
            self._batch_code = batch_code
            self._initial_weight = initial_weight
            self._last_feeding_weight = initial_weight
            self._weight_queue.clear()
            
            # 重新初始化卡尔曼滤波器
            self._kalman_filter = create_weight_filter(initial_weight)
            
            print(f"✅ 投料计算器初始化: 批次={batch_code}, 初始重量={initial_weight:.1f} kg")
    
    def add_measurement(self, 
                       weight: float, 
                       is_discharging: bool, 
                       is_requesting: bool) -> float:
        """添加一次测量数据
        
        Args:
            weight: 测量重量 (kg)
            is_discharging: 排料信号 (%Q3.7)
            is_requesting: 要料信号 (%Q4.0)
            
        Returns:
            滤波后的重量 (kg)
        """
        # 初始化卡尔曼滤波器
        if self._kalman_filter is None:
            self._kalman_filter = create_weight_filter(weight)
            self._initial_weight = weight
            self._last_feeding_weight = weight
        
        # 卡尔曼滤波
        filtered_weight = self._kalman_filter.update(weight, is_discharging)
        
        # 添加到队列
        record = WeightRecord(
            timestamp=datetime.now(),
            raw_weight=weight,
            filtered_weight=filtered_weight,
            is_discharging=is_discharging,
            is_requesting=is_requesting
        )
        
        with self._lock:
            self._weight_queue.append(record)
        
        return filtered_weight
    
    def detect_feeding_segments(self, records: List[WeightRecord]) -> List[FeedingSegment]:
        """检测加料段（重量上升 + 要料信号）
        
        Args:
            records: 重量记录列表
            
        Returns:
            加料段列表
        """
        segments = []
        
        i = 0
        while i < len(records):
            # 查找加料段起点（要料信号=1 且 重量开始上升）
            if records[i].is_requesting:
                start_idx = i
                min_weight = records[i].filtered_weight
                max_weight = records[i].filtered_weight
                min_idx = i
                max_idx = i
                
                # 向后扫描，直到要料信号结束
                j = i + 1
                while j < len(records) and records[j].is_requesting:
                    weight = records[j].filtered_weight
                    
                    if weight < min_weight:
                        min_weight = weight
                        min_idx = j
                    if weight > max_weight:
                        max_weight = weight
                        max_idx = j
                    
                    j += 1
                
                end_idx = j - 1
                
                # 计算加料量（峰值 - 谷值）
                feeding_amount = max_weight - min_weight
                
                # 有效加料段：加料量 >= 5kg（避免误检测）
                if feeding_amount >= 5.0:
                    segment = FeedingSegment(
                        start_idx=start_idx,
                        end_idx=end_idx,
                        min_weight=min_weight,
                        max_weight=max_weight,
                        feeding_amount=feeding_amount,
                        timestamp=records[min_idx].timestamp  # 使用最低点时间戳
                    )
                    segments.append(segment)
                
                i = j
            else:
                i += 1
        
        return segments
    
    def calculate_feeding_amount(self) -> Optional[Dict[str, Any]]:
        """计算15秒窗口内的投料量
        
        Returns:
            {
                'feeding_amount': float,      # 投料量 (kg)
                'added_amount': float,        # 加料量 (kg)
                'start_weight': float,        # 起始重量 (kg)
                'end_weight': float,          # 结束重量 (kg)
                'timestamp': datetime,        # 时间戳
                'confidence': float,          # 置信度 (0-1)
                'feeding_segments': List[FeedingSegment]
            }
            如果没有投料返回 None
        """
        with self._lock:
            # 数据不足
            if len(self._weight_queue) < self.window_size:
                return None
            
            # 取最近30条数据（15秒窗口）
            recent_records = list(self._weight_queue)[-self.window_size:]
            
            # 1. 检测加料段
            feeding_segments = self.detect_feeding_segments(recent_records)
            
            # 2. 计算总加料量
            total_added = sum(seg.feeding_amount for seg in feeding_segments)
            
            # 3. 计算起始和结束重量
            start_weight = recent_records[0].filtered_weight
            end_weight = recent_records[-1].filtered_weight
            
            # 4. 计算净下降量
            net_decrease = start_weight - end_weight
            
            # 5. 计算投料量 = 净下降 + 加料量
            # 公式: 投料量 = (起始 - 结束) + 加料量
            feeding_amount = net_decrease + total_added
            
            # 6. 有效性检查
            if feeding_amount < 5.0:  # 至少5kg才认为是有效投料
                return None
            
            # 7. 计算置信度（基于卡尔曼滤波器）
            confidence = self._kalman_filter.get_confidence() if self._kalman_filter else 0.5
            
            # 8. 更新上次投料重量
            self._last_feeding_weight = end_weight
            
            return {
                'feeding_amount': feeding_amount,
                'added_amount': total_added,
                'start_weight': start_weight,
                'end_weight': end_weight,
                'timestamp': feeding_segments[0].timestamp if feeding_segments else recent_records[0].timestamp,
                'confidence': confidence,
                'feeding_segments': feeding_segments,
                'batch_code': self._batch_code
            }
    
    def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        with self._lock:
            return {
                'queue_size': len(self._weight_queue),
                'max_size': self.queue_size,
                'window_size': self.window_size,
                'last_feeding_weight': self._last_feeding_weight,
                'initial_weight': self._initial_weight,
                'batch_code': self._batch_code
            }
    
    def reset(self):
        """重置计算器"""
        with self._lock:
            self._weight_queue.clear()
            self._kalman_filter = None
            self._last_feeding_weight = None
            self._initial_weight = None
            self._batch_code = None


# ============================================================
# 全局单例
# ============================================================
_feeding_calculator: Optional[FeedingCalculator] = None
_calculator_lock = threading.Lock()


def get_feeding_calculator() -> FeedingCalculator:
    """获取投料计算器单例"""
    global _feeding_calculator
    
    with _calculator_lock:
        if _feeding_calculator is None:
            _feeding_calculator = FeedingCalculator(queue_size=60, window_size=30)
    
    return _feeding_calculator


# ============================================================
# 测试代码
# ============================================================
if __name__ == "__main__":
    import random
    
    print("=" * 70)
    print("智能投料量计算器测试")
    print("=" * 70)
    
    calculator = FeedingCalculator(queue_size=60, window_size=30)
    calculator.initialize_batch("SM20260122-1500", 3500.0)
    
    # 模拟场景：投料 + 加料 + 投料
    print("\n场景: 投料100kg → 加料50kg → 继续投料50kg")
    print("-" * 70)
    
    true_weight = 3500.0
    
    # 阶段1: 投料 (0-10秒, 20次测量)
    print("\n[阶段1] 投料中 (重量下降 100kg)...")
    for i in range(20):
        true_weight -= 5.0  # 每次下降5kg
        noise = random.uniform(-5, 5)
        measurement = true_weight + noise
        
        filtered = calculator.add_measurement(
            weight=measurement,
            is_discharging=True,  # 排料信号
            is_requesting=False
        )
    
    # 计算投料量
    result1 = calculator.calculate_feeding_amount()
    if result1:
        print(f"✅ 检测到投料: {result1['feeding_amount']:.1f} kg")
    
    # 阶段2: 加料 (10-15秒, 10次测量)
    print("\n[阶段2] 加料中 (重量上升 50kg)...")
    for i in range(10):
        true_weight += 5.0  # 每次上升5kg
        noise = random.uniform(-5, 5)
        measurement = true_weight + noise
        
        filtered = calculator.add_measurement(
            weight=measurement,
            is_discharging=False,
            is_requesting=True  # 要料信号
        )
    
    # 阶段3: 继续投料 (15-25秒, 20次测量)
    print("\n[阶段3] 继续投料 (重量下降 50kg)...")
    for i in range(20):
        true_weight -= 2.5  # 每次下降2.5kg
        noise = random.uniform(-5, 5)
        measurement = true_weight + noise
        
        filtered = calculator.add_measurement(
            weight=measurement,
            is_discharging=True,
            is_requesting=False
        )
    
    # 计算投料量
    result2 = calculator.calculate_feeding_amount()
    if result2:
        print(f"\n✅ 检测到投料: {result2['feeding_amount']:.1f} kg")
        print(f"   加料量: {result2['added_amount']:.1f} kg")
        print(f"   净下降: {result2['start_weight'] - result2['end_weight']:.1f} kg")
        print(f"   计算公式: {result2['start_weight'] - result2['end_weight']:.1f} + {result2['added_amount']:.1f} = {result2['feeding_amount']:.1f} kg")
    
    print("\n" + "=" * 70)
    print(f"模拟完成 - 真实投料总量: 150 kg")
    print("=" * 70)
