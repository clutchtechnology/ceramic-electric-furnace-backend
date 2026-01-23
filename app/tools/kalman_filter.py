# ============================================================
# 文件说明: kalman_filter.py - 卡尔曼滤波器（用于料仓重量抗抖动）
# ============================================================
# 功能:
#   1. 实现一维卡尔曼滤波，过滤重量测量噪声（±5kg抖动）
#   2. 提供自适应参数调整功能
#   3. 检测突变（投料/加料）并自动重置
# ============================================================
# 使用场景:
#   - 料仓重量实时测量（0.5秒采样一次）
#   - 过滤传感器抖动（正常抖动 ±5kg）
#   - 保留真实下降趋势（投料时重量下降 10-100kg）
# ============================================================

import math
from typing import Optional, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class FilterState:
    """卡尔曼滤波器状态"""
    estimate: float         # 当前估计值 (kg)
    error_covariance: float # 误差协方差
    measurement_count: int  # 测量次数
    last_update: Optional[datetime] = None


class AdaptiveKalmanFilter:
    """自适应卡尔曼滤波器（专用于料仓重量测量）
    
    原理:
        状态方程: x(k) = x(k-1) + w(k)   # w: 过程噪声
        观测方程: z(k) = x(k) + v(k)     # v: 测量噪声
        
    参数:
        - Q (process_variance): 过程噪声方差，表示重量真实变化速度
          * 投料时：Q较大（重量快速下降）
          * 静止时：Q较小（重量基本不变）
          
        - R (measurement_variance): 测量噪声方差，表示传感器抖动
          * ±5kg 抖动 → R = 5² = 25
          
    自适应策略:
        - 检测到突变（投料）→ 增大Q，快速跟随
        - 稳定期 → 减小Q，平滑输出
    """
    
    def __init__(self,
                 initial_value: float = 3500.0,
                 process_variance: float = 0.1,
                 measurement_variance: float = 25.0,
                 sudden_change_threshold: float = 10.0):
        """初始化卡尔曼滤波器
        
        Args:
            initial_value: 初始重量估计值 (kg)
            process_variance: 过程噪声方差 Q (默认 0.1，表示静止状态)
            measurement_variance: 测量噪声方差 R (默认 25 = 5kg²)
            sudden_change_threshold: 突变检测阈值 (默认 10kg)
        """
        self.Q = process_variance
        self.R = measurement_variance
        self.sudden_change_threshold = sudden_change_threshold
        
        # 初始化状态
        self.state = FilterState(
            estimate=initial_value,
            error_covariance=self.R,  # 初始不确定性等于测量噪声
            measurement_count=0,
            last_update=None
        )
        
        # 自适应参数
        self.Q_static = 0.1     # 静止时的Q
        self.Q_feeding = 5.0    # 投料时的Q
        self.is_feeding = False # 当前是否在投料
        
        # 历史记录（用于突变检测）
        self.last_measurement: Optional[float] = None
        self.innovation_history = []  # 新息序列（实测-预测）
        
    def update(self, measurement: float, is_discharging: bool = False) -> float:
        """更新滤波器并返回估计值
        
        Args:
            measurement: 当前测量值 (kg)
            is_discharging: 是否正在投料（PLC信号 %Q3.7）
            
        Returns:
            滤波后的估计值 (kg)
        """
        # 1. 自适应调整Q（根据投料状态）
        if is_discharging:
            self.Q = self.Q_feeding  # 投料时，允许快速变化
            self.is_feeding = True
        else:
            self.Q = self.Q_static   # 静止时，强力平滑
            self.is_feeding = False
        
        # 2. 预测步骤
        # x̂(k|k-1) = x̂(k-1|k-1)  (假设重量不变)
        prediction = self.state.estimate
        
        # P(k|k-1) = P(k-1|k-1) + Q
        prediction_covariance = self.state.error_covariance + self.Q
        
        # 3. 计算新息（Innovation）
        innovation = measurement - prediction
        self.innovation_history.append(innovation)
        if len(self.innovation_history) > 10:
            self.innovation_history.pop(0)
        
        # 4. 突变检测（投料开始/结束）
        if abs(innovation) > self.sudden_change_threshold and not is_discharging:
            # 检测到非投料时的突变 → 可能是加料或传感器故障
            # 增大测量噪声，减少信任度
            effective_R = self.R * 2.0
        else:
            effective_R = self.R
        
        # 5. 更新步骤
        # K(k) = P(k|k-1) / [P(k|k-1) + R]  (卡尔曼增益)
        innovation_covariance = prediction_covariance + effective_R
        kalman_gain = prediction_covariance / innovation_covariance
        
        # x̂(k|k) = x̂(k|k-1) + K(k) * [z(k) - x̂(k|k-1)]
        self.state.estimate = prediction + kalman_gain * innovation
        
        # P(k|k) = [1 - K(k)] * P(k|k-1)
        self.state.error_covariance = (1 - kalman_gain) * prediction_covariance
        
        # 6. 更新状态
        self.state.measurement_count += 1
        self.state.last_update = datetime.now()
        self.last_measurement = measurement
        
        return self.state.estimate
    
    def get_confidence(self) -> float:
        """获取当前估计的置信度（0-1）
        
        Returns:
            置信度: 1.0 = 完全可信, 0.0 = 完全不可信
        """
        # 基于误差协方差计算置信度
        # P越小 → 置信度越高
        max_uncertainty = self.R * 2  # 最大不确定性
        confidence = 1.0 - min(self.state.error_covariance / max_uncertainty, 1.0)
        return confidence
    
    def reset(self, new_value: Optional[float] = None):
        """重置滤波器
        
        Args:
            new_value: 新的初始值，None则使用当前估计值
        """
        if new_value is not None:
            self.state.estimate = new_value
        self.state.error_covariance = self.R
        self.state.measurement_count = 0
        self.innovation_history.clear()
        self.last_measurement = None
    
    def get_state(self) -> FilterState:
        """获取当前状态"""
        return self.state
    
    def get_innovation_std(self) -> float:
        """获取新息标准差（用于异常检测）"""
        if len(self.innovation_history) < 2:
            return 0.0
        
        mean = sum(self.innovation_history) / len(self.innovation_history)
        variance = sum((x - mean)**2 for x in self.innovation_history) / len(self.innovation_history)
        return math.sqrt(variance)


# ============================================================
# 便捷函数
# ============================================================
def create_weight_filter(initial_weight: float = 3500.0) -> AdaptiveKalmanFilter:
    """创建适合料仓重量测量的卡尔曼滤波器
    
    Args:
        initial_weight: 初始重量 (kg)
        
    Returns:
        配置好的卡尔曼滤波器
    """
    return AdaptiveKalmanFilter(
        initial_value=initial_weight,
        process_variance=0.1,        # 静止时重量几乎不变
        measurement_variance=25.0,   # 传感器抖动 ±5kg
        sudden_change_threshold=10.0 # 10kg以上视为突变
    )


# ============================================================
# 测试代码
# ============================================================
if __name__ == "__main__":
    import random
    
    print("=" * 70)
    print("卡尔曼滤波器测试 - 料仓重量抗抖动")
    print("=" * 70)
    
    # 模拟场景：初始重量3500kg，投料过程下降到3400kg
    true_weight = 3500.0
    kf = create_weight_filter(initial_weight=3500.0)
    
    print("\n场景1: 静止状态（±5kg抖动）")
    print("-" * 70)
    print(f"{'时刻':<6} {'真实值':<10} {'测量值':<10} {'滤波值':<10} {'置信度':<10}")
    print("-" * 70)
    
    for i in range(10):
        # 添加 ±5kg 随机噪声
        noise = random.uniform(-5, 5)
        measurement = true_weight + noise
        
        filtered = kf.update(measurement, is_discharging=False)
        confidence = kf.get_confidence()
        
        print(f"{i:<6} {true_weight:<10.1f} {measurement:<10.1f} {filtered:<10.1f} {confidence:<10.3f}")
    
    print("\n场景2: 投料过程（重量下降 3500 → 3400kg，持续15秒）")
    print("-" * 70)
    print(f"{'时刻':<6} {'真实值':<10} {'测量值':<10} {'滤波值':<10} {'投料信号':<10}")
    print("-" * 70)
    
    # 模拟投料：每0.5秒下降约3.3kg，共30次测量
    for i in range(30):
        true_weight -= 3.3  # 100kg / 30 = 3.3kg per step
        noise = random.uniform(-5, 5)
        measurement = true_weight + noise
        
        # 前20次投料，后10次停止
        is_discharging = i < 20
        
        filtered = kf.update(measurement, is_discharging=is_discharging)
        
        print(f"{i:<6} {true_weight:<10.1f} {measurement:<10.1f} {filtered:<10.1f} {is_discharging!s:<10}")
    
    print("\n场景3: 投料结束后稳定")
    print("-" * 70)
    
    for i in range(10):
        noise = random.uniform(-5, 5)
        measurement = true_weight + noise
        
        filtered = kf.update(measurement, is_discharging=False)
        
        print(f"{i:<6} {true_weight:<10.1f} {measurement:<10.1f} {filtered:<10.1f}")
    
    print("\n" + "=" * 70)
    print("测试完成")
    print(f"最终估计值: {kf.state.estimate:.2f} kg")
    print(f"真实值: {true_weight:.2f} kg")
    print(f"误差: {abs(kf.state.estimate - true_weight):.2f} kg")
    print(f"置信度: {kf.get_confidence():.3f}")
    print("=" * 70)
