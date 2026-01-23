# ============================================================
# 文件说明: test_feeding_calculation.py - 投料计算完整测试
# ============================================================
# 用法:
#   cd D:\furnace-backend
#   venv\Scripts\python scripts\test_feeding_calculation.py
# ============================================================

import sys
sys.path.insert(0, '.')

from app.services.feeding_calculator import FeedingCalculator
import random
import time


def test_simple_feeding():
    """测试1: 简单投料（无加料）"""
    print("\n" + "=" * 70)
    print("测试1: 简单投料 (3500kg → 3400kg, 持续15秒)")
    print("=" * 70)
    
    calculator = FeedingCalculator(queue_size=60, window_size=30)
    calculator.initialize_batch("SM20260122-1500", 3500.0)
    
    true_weight = 3500.0
    
    # 模拟30次测量（15秒）
    for i in range(30):
        true_weight -= 100.0 / 30  # 均匀下降
        noise = random.uniform(-5, 5)
        measurement = true_weight + noise
        
        filtered = calculator.add_measurement(
            weight=measurement,
            is_discharging=True,
            is_requesting=False
        )
    
    # 计算投料量
    result = calculator.calculate_feeding_amount()
    
    if result:
        print(f"\n✅ 投料量: {result['feeding_amount']:.1f} kg")
        print(f"   起始重量: {result['start_weight']:.1f} kg")
        print(f"   结束重量: {result['end_weight']:.1f} kg")
        print(f"   加料量: {result['added_amount']:.1f} kg")
        print(f"   置信度: {result['confidence']:.3f}")
        
        error = abs(result['feeding_amount'] - 100.0)
        print(f"\n   误差: {error:.2f} kg ({error/100*100:.1f}%)")
    else:
        print("❌ 未检测到投料")


def test_feeding_with_addition():
    """测试2: 投料过程中加料"""
    print("\n" + "=" * 70)
    print("测试2: 投料 + 中途加料 + 继续投料")
    print("=" * 70)
    
    calculator = FeedingCalculator(queue_size=60, window_size=30)
    calculator.initialize_batch("SM20260122-1501", 3500.0)
    
    true_weight = 3500.0
    
    print("\n阶段 | 时间  | 动作      | 真实重量")
    print("-" * 50)
    
    # 阶段1: 投料50kg (0-5秒, 10次)
    print("  1   | 0-5s  | 投料      | 3500 → 3450")
    for i in range(10):
        true_weight -= 5.0
        noise = random.uniform(-5, 5)
        calculator.add_measurement(true_weight + noise, True, False)
    
    # 阶段2: 加料30kg (5-8秒, 6次)
    print("  2   | 5-8s  | 加料      | 3450 → 3480")
    for i in range(6):
        true_weight += 5.0
        noise = random.uniform(-5, 5)
        calculator.add_measurement(true_weight + noise, False, True)
    
    # 阶段3: 继续投料50kg (8-15秒, 14次)
    print("  3   | 8-15s | 继续投料  | 3480 → 3430")
    for i in range(14):
        true_weight -= 50.0 / 14
        noise = random.uniform(-5, 5)
        calculator.add_measurement(true_weight + noise, True, False)
    
    # 计算投料量
    result = calculator.calculate_feeding_amount()
    
    if result:
        print("\n" + "-" * 50)
        print("计算结果:")
        print(f"  净下降量: {result['start_weight'] - result['end_weight']:.1f} kg")
        print(f"  加料量:   {result['added_amount']:.1f} kg")
        print(f"  投料量:   {result['feeding_amount']:.1f} kg")
        print(f"\n  计算公式: {result['start_weight'] - result['end_weight']:.1f} + {result['added_amount']:.1f} = {result['feeding_amount']:.1f} kg")
        
        # 真实投料 = 50 + 50 = 100kg
        error = abs(result['feeding_amount'] - 100.0)
        print(f"\n  真实投料: 100.0 kg")
        print(f"  计算误差: {error:.2f} kg ({error/100*100:.1f}%)")


def test_multiple_additions():
    """测试3: 多次加料"""
    print("\n" + "=" * 70)
    print("测试3: 投料过程中多次加料")
    print("=" * 70)
    
    calculator = FeedingCalculator(queue_size=60, window_size=30)
    calculator.initialize_batch("SM20260122-1502", 3500.0)
    
    true_weight = 3500.0
    sequence = []
    
    # 复杂场景: 投-加-投-加-投
    steps = [
        (10, -3.0, True, False, "投料30kg"),
        (5, 4.0, False, True, "加料20kg"),
        (5, -2.0, True, False, "投料10kg"),
        (5, 3.0, False, True, "加料15kg"),
        (5, -5.0, True, False, "投料25kg"),
    ]
    
    print("\n阶段 | 动作       | 次数 | 单次变化 | 累计重量")
    print("-" * 60)
    
    for i, (count, delta, discharge, request, desc) in enumerate(steps, 1):
        start_w = true_weight
        for _ in range(count):
            true_weight += delta
            noise = random.uniform(-5, 5)
            calculator.add_measurement(true_weight + noise, discharge, request)
        
        print(f"  {i}   | {desc:10s} | {count:2d}次 | {delta:+5.1f}kg | {start_w:.0f} → {true_weight:.0f}")
    
    # 计算投料量
    result = calculator.calculate_feeding_amount()
    
    if result:
        print("\n" + "-" * 60)
        print("计算结果:")
        print(f"  加料段数: {len(result['feeding_segments'])}")
        for i, seg in enumerate(result['feeding_segments'], 1):
            print(f"    段{i}: {seg.feeding_amount:.1f} kg (谷值={seg.min_weight:.1f}, 峰值={seg.max_weight:.1f})")
        
        print(f"\n  总加料量: {result['added_amount']:.1f} kg")
        print(f"  净下降:   {result['start_weight'] - result['end_weight']:.1f} kg")
        print(f"  投料量:   {result['feeding_amount']:.1f} kg")
        
        # 真实投料 = 30 + 10 + 25 = 65kg
        true_feeding = 30 + 10 + 25
        error = abs(result['feeding_amount'] - true_feeding)
        print(f"\n  真实投料: {true_feeding} kg")
        print(f"  计算误差: {error:.2f} kg ({error/true_feeding*100:.1f}%)")


def test_edge_cases():
    """测试4: 边界情况"""
    print("\n" + "=" * 70)
    print("测试4: 边界情况测试")
    print("=" * 70)
    
    calculator = FeedingCalculator(queue_size=60, window_size=30)
    calculator.initialize_batch("SM20260122-1503", 3500.0)
    
    # 情况1: 重量基本不变（抖动）
    print("\n情况1: 重量抖动（±5kg），无实际投料")
    true_weight = 3500.0
    for i in range(30):
        noise = random.uniform(-5, 5)
        calculator.add_measurement(true_weight + noise, False, False)
    
    result = calculator.calculate_feeding_amount()
    if result:
        print(f"  ❌ 错误检测到投料: {result['feeding_amount']:.1f} kg")
    else:
        print(f"  ✅ 正确: 未检测到投料")
    
    # 情况2: 小量投料（<5kg）
    print("\n情况2: 小量投料（3kg）")
    calculator.reset()
    calculator.initialize_batch("SM20260122-1504", 3500.0)
    
    true_weight = 3500.0
    for i in range(30):
        true_weight -= 3.0 / 30
        noise = random.uniform(-5, 5)
        calculator.add_measurement(true_weight + noise, True, False)
    
    result = calculator.calculate_feeding_amount()
    if result:
        print(f"  检测到投料: {result['feeding_amount']:.1f} kg")
    else:
        print(f"  ✅ 正确: 投料量太小，未计入")


# ============================================================
# 主函数
# ============================================================
if __name__ == "__main__":
    print("=" * 70)
    print("智能投料量计算 - 综合测试")
    print("=" * 70)
    
    test_simple_feeding()
    test_feeding_with_addition()
    test_multiple_additions()
    test_edge_cases()
    
    print("\n" + "=" * 70)
    print("所有测试完成！")
    print("=" * 70)
    print("\n算法总结:")
    print("  投料量 = (起始重量 - 结束重量) + 加料量")
    print("  - 自动检测加料段（要料信号 + 重量上升）")
    print("  - 使用卡尔曼滤波抗±5kg抖动")
    print("  - 15秒滑动窗口（30条数据点）")
    print("  - 最小有效投料量: 5kg")
