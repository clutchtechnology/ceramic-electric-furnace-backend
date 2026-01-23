# ============================================================
# 文件说明: test_kalman_filter.py - 卡尔曼滤波器测试脚本
# ============================================================
# 用法:
#   cd D:\furnace-backend
#   venv\Scripts\python scripts\test_kalman_filter.py
# ============================================================

import sys
sys.path.insert(0, '.')

from app.tools.kalman_filter import AdaptiveKalmanFilter, create_weight_filter
import random
import time

def test_basic_filtering():
    """测试1: 基础滤波能力（静止状态抗抖动）"""
    print("\n" + "=" * 70)
    print("测试1: 基础滤波能力（静止状态 ±5kg 抖动）")
    print("=" * 70)
    
    true_weight = 3500.0
    kf = create_weight_filter(initial_weight=3500.0)
    
    measurements = []
    filtered_values = []
    
    print(f"{'时刻':<6} {'真实值':<10} {'测量值':<10} {'滤波值':<10} {'误差':<10} {'置信度':<10}")
    print("-" * 70)
    
    for i in range(20):
        # 添加随机噪声
        noise = random.uniform(-5, 5)
        measurement = true_weight + noise
        measurements.append(measurement)
        
        # 滤波
        filtered = kf.update(measurement, is_discharging=False)
        filtered_values.append(filtered)
        
        error = abs(filtered - true_weight)
        confidence = kf.get_confidence()
        
        print(f"{i:<6} {true_weight:<10.1f} {measurement:<10.1f} {filtered:<10.1f} {error:<10.2f} {confidence:<10.3f}")
    
    # 统计
    avg_measurement_error = sum(abs(m - true_weight) for m in measurements) / len(measurements)
    avg_filtered_error = sum(abs(f - true_weight) for f in filtered_values) / len(filtered_values)
    
    print("-" * 70)
    print(f"测量值平均误差: {avg_measurement_error:.2f} kg")
    print(f"滤波值平均误差: {avg_filtered_error:.2f} kg")
    print(f"误差降低: {(1 - avg_filtered_error/avg_measurement_error)*100:.1f}%")


def test_feeding_tracking():
    """测试2: 投料过程跟踪能力"""
    print("\n" + "=" * 70)
    print("测试2: 投料过程跟踪（3500kg → 3400kg，持续15秒）")
    print("=" * 70)
    
    true_weight = 3500.0
    kf = create_weight_filter(initial_weight=3500.0)
    
    print(f"{'时刻(s)':<8} {'真实值':<10} {'测量值':<10} {'滤波值':<10} {'投料':<6} {'滞后':<10}")
    print("-" * 70)
    
    # 模拟30次测量（15秒，每0.5秒一次）
    for i in range(30):
        # 真实重量下降
        if i < 20:  # 前10秒投料
            true_weight -= 5.0  # 100kg / 20 = 5kg per step
        
        # 添加噪声
        noise = random.uniform(-5, 5)
        measurement = true_weight + noise
        
        # 滤波（带投料信号）
        is_discharging = i < 20
        filtered = kf.update(measurement, is_discharging=is_discharging)
        
        lag = filtered - true_weight  # 滞后量（正值表示滤波值高于真实值）
        
        time_sec = i * 0.5
        print(f"{time_sec:<8.1f} {true_weight:<10.1f} {measurement:<10.1f} {filtered:<10.1f} {'投料' if is_discharging else '停止':<6} {lag:<10.2f}")
    
    print("-" * 70)
    print(f"最终重量: {true_weight:.1f} kg")
    print(f"滤波估计: {kf.state.estimate:.1f} kg")
    print(f"估计误差: {abs(kf.state.estimate - true_weight):.2f} kg")


def test_sudden_change_detection():
    """测试3: 突变检测（加料/故障）"""
    print("\n" + "=" * 70)
    print("测试3: 突变检测（第10次测量突然加料50kg）")
    print("=" * 70)
    
    true_weight = 3400.0
    kf = create_weight_filter(initial_weight=3400.0)
    
    print(f"{'时刻':<6} {'真实值':<10} {'测量值':<10} {'滤波值':<10} {'新息':<10} {'新息std':<10}")
    print("-" * 70)
    
    for i in range(20):
        # 第10次测量时加料
        if i == 10:
            true_weight += 50.0
            print(">>> 突然加料 50kg <<<")
        
        noise = random.uniform(-5, 5)
        measurement = true_weight + noise
        
        filtered = kf.update(measurement, is_discharging=False)
        
        # 获取新息（实测-预测）
        innovation = measurement - (kf.state.estimate - (measurement - kf.state.estimate) * (kf.state.error_covariance / (kf.state.error_covariance + kf.R)))
        innovation_std = kf.get_innovation_std()
        
        print(f"{i:<6} {true_weight:<10.1f} {measurement:<10.1f} {filtered:<10.1f} {innovation:<10.2f} {innovation_std:<10.2f}")


def test_comparison_with_raw():
    """测试4: 原始数据 vs 滤波数据对比"""
    print("\n" + "=" * 70)
    print("测试4: 投料量计算对比（原始数据 vs 滤波数据）")
    print("=" * 70)
    
    true_start_weight = 3500.0
    true_end_weight = 3400.0
    true_feeding = true_start_weight - true_end_weight  # 100kg
    
    kf = create_weight_filter(initial_weight=3500.0)
    
    raw_measurements = []
    filtered_values = []
    
    # 模拟30次投料测量
    true_weight = true_start_weight
    for i in range(30):
        true_weight -= 100.0 / 30  # 均匀下降
        
        noise = random.uniform(-5, 5)
        measurement = true_weight + noise
        raw_measurements.append(measurement)
        
        filtered = kf.update(measurement, is_discharging=True)
        filtered_values.append(filtered)
    
    # 计算投料量
    raw_feeding = raw_measurements[0] - raw_measurements[-1]
    filtered_feeding = filtered_values[0] - filtered_values[-1]
    
    print(f"真实投料量:   {true_feeding:.2f} kg")
    print(f"原始数据计算: {raw_feeding:.2f} kg (误差: {abs(raw_feeding - true_feeding):.2f} kg)")
    print(f"滤波数据计算: {filtered_feeding:.2f} kg (误差: {abs(filtered_feeding - true_feeding):.2f} kg)")
    print(f"\n滤波改善: {(1 - abs(filtered_feeding - true_feeding) / abs(raw_feeding - true_feeding)) * 100:.1f}%")


# ============================================================
# 主函数
# ============================================================
if __name__ == "__main__":
    print("=" * 70)
    print("卡尔曼滤波器综合测试 - 料仓重量应用")
    print("=" * 70)
    
    # 运行所有测试
    test_basic_filtering()
    test_feeding_tracking()
    test_sudden_change_detection()
    test_comparison_with_raw()
    
    print("\n" + "=" * 70)
    print("所有测试完成！")
    print("=" * 70)
    print("\n推荐配置:")
    print("  - process_variance (Q) = 0.1  (静止时)")
    print("  - process_variance (Q) = 5.0  (投料时)")
    print("  - measurement_variance (R) = 25.0  (±5kg噪声)")
    print("  - sudden_change_threshold = 10.0 kg")
