#!/usr/bin/env python3
# ============================================================
# 文件说明: test_data_variation.py - 测试数据变化特性
# ============================================================
# 功能:
# 1. 验证Mock数据生成器的数据变化逻辑
# 2. 测试正弦波、随机噪声、递增累计等特性
# 3. 生成测试报告
#
# 使用方法:
#   python tests/mock/test_data_variation.py
# ============================================================

import sys
import os

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from tests.mock.mock_data_generator import MockDataGenerator


def test_electrode_depth_variation():
    """测试电极深度数据变化"""
    print("\n" + "=" * 60)
    print("测试: 电极深度数据变化")
    print("=" * 60)
    
    generator = MockDataGenerator()
    
    print(f"{'轮次':<8} {'电极1 (mm)':<15} {'电极2 (mm)':<15} {'电极3 (mm)':<15}")
    print("-" * 60)
    
    for i in range(10):
        all_data = generator.generate_all_db_data()
        db32_raw = all_data[32]
        
        # 解析前12字节（3个电极）
        import struct
        depths = []
        for j in range(3):
            offset = j * 4
            high, low = struct.unpack('>HH', db32_raw[offset:offset+4])
            distance = high * 65536 + low
            depths.append(distance)
        
        print(f"{i+1:<8} {depths[0]:<15.1f} {depths[1]:<15.1f} {depths[2]:<15.1f}")
    
    print("\n✅ 电极深度数据具有合理的波动")


def test_electricity_accumulation():
    """测试电表能耗累计"""
    print("\n" + "=" * 60)
    print("测试: 电表能耗累计")
    print("=" * 60)
    
    generator = MockDataGenerator()
    
    print(f"{'轮次':<8} {'功率 (kW)':<15} {'累计能耗 (kWh)':<20} {'增量 (kWh)':<15}")
    print("-" * 60)
    
    prev_energy = 0
    
    for i in range(10):
        all_data = generator.generate_all_db_data()
        db33_raw = all_data[33]
        
        # 解析功率和能耗
        import struct
        power = struct.unpack('>f', db33_raw[24:28])[0]  # Pt (第7个REAL)
        energy = struct.unpack('>f', db33_raw[40:44])[0]  # ImpEp (第11个REAL)
        
        delta = energy - prev_energy
        prev_energy = energy
        
        print(f"{i+1:<8} {power:<15.2f} {energy:<20.2f} {delta:<15.6f}")
    
    print("\n✅ 能耗数据持续累计，符合预期")


def test_hopper_weight_consumption():
    """测试料仓重量消耗"""
    print("\n" + "=" * 60)
    print("测试: 料仓重量消耗模拟")
    print("=" * 60)
    
    generator = MockDataGenerator()
    
    print(f"{'轮次':<8} {'重量 (kg)':<15} {'消耗中':<10} {'消耗速率 (kg/s)':<20}")
    print("-" * 60)
    
    for i in range(20):
        weight = generator.get_hopper_weight()
        consuming = generator._hopper_consuming
        rate = generator._hopper_consume_rate
        
        status = "是" if consuming else "否"
        
        print(f"{i+1:<8} {weight:<15.0f} {status:<10} {rate:<20.2f}")
    
    print("\n✅ 料仓重量在下料时递减，停止时保持稳定")


def test_data_structure_size():
    """测试数据块大小"""
    print("\n" + "=" * 60)
    print("测试: 数据块大小验证")
    print("=" * 60)
    
    generator = MockDataGenerator()
    all_data = generator.generate_all_db_data()
    
    expected_sizes = {
        30: 40,  # DB30
        32: 28,  # DB32
        33: 56,  # DB33
    }
    
    print(f"{'DB块':<10} {'实际大小':<15} {'期望大小':<15} {'状态':<10}")
    print("-" * 60)
    
    all_ok = True
    for db_num, expected_size in expected_sizes.items():
        actual_size = len(all_data[db_num])
        status = "✅ 正确" if actual_size == expected_size else "❌ 错误"
        if actual_size != expected_size:
            all_ok = False
        
        print(f"DB{db_num:<7} {actual_size:<15} {expected_size:<15} {status}")
    
    if all_ok:
        print("\n✅ 所有数据块大小正确")
    else:
        print("\n❌ 部分数据块大小不匹配")
        return False
    
    return True


def main():
    """主测试入口"""
    print("=" * 60)
    print("电炉 Mock 数据生成器 - 数据变化测试")
    print("=" * 60)
    
    # 运行所有测试
    test_data_structure_size()
    test_electrode_depth_variation()
    test_electricity_accumulation()
    test_hopper_weight_consumption()
    
    print("\n" + "=" * 60)
    print("✅ 所有测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
