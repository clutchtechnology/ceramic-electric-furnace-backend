"""
单元测试：批次续炼测试
测试场景：
1. 开始冶炼（批次号 TEST001）
2. 10秒后停止冶炼
3. 5秒后再次开始冶炼（相同批次号 TEST001）
4. 验证投料重量和累计水用量是否继续累计，不归零
"""

import sys
import time
from datetime import datetime, timezone

# 添加项目路径
sys.path.insert(0, 'c:\\Users\\20216\\Documents\\GitHub\\Clutch\\ceramic-electric-furnace-backend')

from app.services.batch_service import get_batch_service
from app.services.feeding_accumulator import get_feeding_accumulator
from app.services.cooling_water_calculator import get_cooling_water_calculator


def print_section(title):
    """打印分隔线"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_feeding_status():
    """打印投料状态"""
    feeding_acc = get_feeding_accumulator()
    status = feeding_acc.get_realtime_data()
    print(f"  投料状态:")
    print(f"    - 当前重量: {status['current_weight']:.1f} kg")
    print(f"    - 累计投料: {status['feeding_total']:.1f} kg")
    print(f"    - 投料次数: {status['feeding_count']}")
    print(f"    - 是否排料: {status['is_discharging']}")
    return status['feeding_total']


def print_cooling_status():
    """打印冷却水状态"""
    cooling_calc = get_cooling_water_calculator()
    volumes = cooling_calc.get_total_volumes()
    realtime = cooling_calc.get_realtime_data()
    print(f"  冷却水状态:")
    print(f"    - 炉盖累计: {volumes['furnace_cover']:.4f} m³")
    print(f"    - 炉皮累计: {volumes['furnace_shell']:.4f} m³")
    print(f"    - 炉盖流速: {realtime['furnace_cover_flow']:.2f} m³/h")
    print(f"    - 炉皮流速: {realtime['furnace_shell_flow']:.2f} m³/h")
    return volumes['furnace_cover'], volumes['furnace_shell']


def simulate_feeding(weight_kg, is_discharging=False):
    """模拟投料数据"""
    feeding_acc = get_feeding_accumulator()
    result = feeding_acc.add_measurement(
        weight_kg=weight_kg,
        is_discharging=is_discharging,
        is_requesting=False
    )
    # 如果需要计算，调用计算方法
    if result.get('should_calc'):
        feeding_acc.calculate_feeding()
    return result


def simulate_cooling_water(cover_flow, shell_flow, cover_pressure, shell_pressure):
    """模拟冷却水数据"""
    cooling_calc = get_cooling_water_calculator()
    result = cooling_calc.add_measurement(
        furnace_cover_flow=cover_flow,
        furnace_shell_flow=shell_flow,
        furnace_cover_pressure=cover_pressure,
        furnace_shell_pressure=shell_pressure
    )
    # 如果需要计算，调用计算方法
    if result.get('should_calc_volume'):
        cooling_calc.calculate_volume_increment()
    return result


def main():
    print_section("批次续炼测试 - 开始")
    
    batch_service = get_batch_service()
    test_batch_code = "TEST001"
    
    # ============================================================
    # 第0步：先停止现有冶炼（如果有）
    # ============================================================
    print_section("第0步：停止现有冶炼（如果有）")
    if batch_service.is_running:
        result = batch_service.stop()
        print(f"  结果: {result['message']}")
        time.sleep(1)
    else:
        print(f"  当前状态: {batch_service.state.value} (无需停止)")
    
    # ============================================================
    # 第1步：开始冶炼（批次号 TEST001）
    # ============================================================
    print_section("第1步：开始冶炼（批次号 TEST001）")
    result = batch_service.start(test_batch_code)
    print(f"  结果: {result['message']}")
    print(f"  批次号: {result['batch_code']}")
    
    # ============================================================
    # 第2步：模拟投料和冷却水数据（持续35秒）
    # ============================================================
    print_section("第2步：模拟投料和冷却水数据（35秒）")
    print("  说明: 投料累计器每30秒计算一次，冷却水每15秒计算一次")
    
    # 初始状态
    feeding_total_1 = print_feeding_status()
    cover_total_1, shell_total_1 = print_cooling_status()
    
    print("\n  开始模拟数据...")
    
    # 模拟35秒的数据（投料每0.5秒一次，冷却水每0.5秒一次）
    # 投料累计器每30秒计算一次（60次轮询），冷却水每15秒计算一次（30次轮询）
    for i in range(70):  # 70次 × 0.5秒 = 35秒
        # 模拟投料：重量从1000kg降到650kg（投料350kg）
        weight = 1000 - (i * 5)
        simulate_feeding(weight, is_discharging=True)

        # 模拟冷却水：流速 10 m³/h
        simulate_cooling_water(
            cover_flow=10.0,
            shell_flow=12.0,
            cover_pressure=300.0,  # kPa
            shell_pressure=350.0   # kPa
        )

        time.sleep(0.5)

        # 每15秒打印一次状态（冷却水计算触发点）
        if (i + 1) % 30 == 0:
            print(f"\n  --- 经过 {(i + 1) * 0.5:.1f} 秒 (冷却水计算触发) ---")
            print_feeding_status()
            print_cooling_status()
        # 每30秒打印一次状态（投料计算触发点）
        elif (i + 1) % 60 == 0:
            print(f"\n  --- 经过 {(i + 1) * 0.5:.1f} 秒 (投料计算触发) ---")
            print_feeding_status()
            print_cooling_status()
    
    # 35秒后的状态
    print("\n  35秒后的状态:")
    feeding_total_2 = print_feeding_status()
    cover_total_2, shell_total_2 = print_cooling_status()
    
    # 计算增量
    feeding_delta_1 = feeding_total_2 - feeding_total_1
    cover_delta_1 = cover_total_2 - cover_total_1
    shell_delta_1 = shell_total_2 - shell_total_1
    
    print(f"\n  第1阶段增量:")
    print(f"    - 投料增量: {feeding_delta_1:.1f} kg")
    print(f"    - 炉盖水增量: {cover_delta_1:.4f} m³")
    print(f"    - 炉皮水增量: {shell_delta_1:.4f} m³")
    
    # ============================================================
    # 第3步：停止冶炼
    # ============================================================
    print_section("第3步：停止冶炼")
    result = batch_service.stop()
    print(f"  结果: {result['message']}")
    summary = result.get('summary', {})
    print(f"  批次号: {summary.get('batch_code', 'N/A')}")
    
    # 停止后的状态
    feeding_total_stop = print_feeding_status()
    cover_total_stop, shell_total_stop = print_cooling_status()
    
    # ============================================================
    # 第4步：等待5秒
    # ============================================================
    print_section("第4步：等待5秒")
    print("  等待中...")
    time.sleep(5)
    
    # ============================================================
    # 第5步：再次开始冶炼（相同批次号 TEST001）
    # ============================================================
    print_section("第5步：再次开始冶炼（相同批次号 TEST001）")
    result = batch_service.start(test_batch_code)
    print(f"  结果: {result['message']}")
    print(f"  批次号: {result['batch_code']}")
    
    # 检查累计值是否归零
    print("\n  检查累计值是否归零:")
    feeding_total_3 = print_feeding_status()
    cover_total_3, shell_total_3 = print_cooling_status()
    
    # ============================================================
    # 第6步：继续模拟数据（35秒）
    # ============================================================
    print_section("第6步：继续模拟数据（35秒）")
    print("  说明: 投料累计器每30秒计算一次，冷却水每15秒计算一次")
    
    print("\n  开始模拟数据...")
    
    for i in range(70):  # 70次 × 0.5秒 = 35秒
        # 模拟投料：重量从650kg降到300kg（投料350kg）
        weight = 650 - (i * 5)
        simulate_feeding(weight, is_discharging=True)

        # 模拟冷却水：流速 10 m³/h
        simulate_cooling_water(
            cover_flow=10.0,
            shell_flow=12.0,
            cover_pressure=300.0,
            shell_pressure=350.0
        )

        time.sleep(0.5)

        # 每15秒打印一次状态（冷却水计算触发点）
        if (i + 1) % 30 == 0:
            print(f"\n  --- 经过 {(i + 1) * 0.5:.1f} 秒 (冷却水计算触发) ---")
            print_feeding_status()
            print_cooling_status()
        # 每30秒打印一次状态（投料计算触发点）
        elif (i + 1) % 60 == 0:
            print(f"\n  --- 经过 {(i + 1) * 0.5:.1f} 秒 (投料计算触发) ---")
            print_feeding_status()
            print_cooling_status()
    
    # 35秒后的状态
    print("\n  35秒后的状态:")
    feeding_total_4 = print_feeding_status()
    cover_total_4, shell_total_4 = print_cooling_status()
    
    # 计算第2阶段增量
    feeding_delta_2 = feeding_total_4 - feeding_total_3
    cover_delta_2 = cover_total_4 - cover_total_3
    shell_delta_2 = shell_total_4 - shell_total_3
    
    print(f"\n  第2阶段增量:")
    print(f"    - 投料增量: {feeding_delta_2:.1f} kg")
    print(f"    - 炉盖水增量: {cover_delta_2:.4f} m³")
    print(f"    - 炉皮水增量: {shell_delta_2:.4f} m³")
    
    # ============================================================
    # 第7步：验证结果
    # ============================================================
    print_section("第7步：验证结果")
    
    print("\n  数据汇总:")
    print(f"    第1阶段结束:")
    print(f"      - 投料累计: {feeding_total_2:.1f} kg")
    print(f"      - 炉盖水累计: {cover_total_2:.4f} m³")
    print(f"      - 炉皮水累计: {shell_total_2:.4f} m³")
    
    print(f"\n    停止后:")
    print(f"      - 投料累计: {feeding_total_stop:.1f} kg")
    print(f"      - 炉盖水累计: {cover_total_stop:.4f} m³")
    print(f"      - 炉皮水累计: {shell_total_stop:.4f} m³")
    
    print(f"\n    第2阶段开始（续炼）:")
    print(f"      - 投料累计: {feeding_total_3:.1f} kg")
    print(f"      - 炉盖水累计: {cover_total_3:.4f} m³")
    print(f"      - 炉皮水累计: {shell_total_3:.4f} m³")
    
    print(f"\n    第2阶段结束:")
    print(f"      - 投料累计: {feeding_total_4:.1f} kg")
    print(f"      - 炉盖水累计: {cover_total_4:.4f} m³")
    print(f"      - 炉皮水累计: {shell_total_4:.4f} m³")
    
    # 验证是否归零
    print("\n  验证结果:")
    
    # 判断归零：续炼开始时的累计值应该等于停止时的累计值（保持不变）
    # 如果续炼开始时归零了，说明有问题
    feeding_reset = abs(feeding_total_3) < 0.01  # 续炼开始时是否归零
    cover_reset = abs(cover_total_3) < 0.0001
    shell_reset = abs(shell_total_3) < 0.0001
    
    # 判断是否保持：续炼开始时的累计值应该等于停止时的累计值
    feeding_kept = abs(feeding_total_3 - feeding_total_stop) < 0.01
    cover_kept = abs(cover_total_3 - cover_total_stop) < 0.0001
    shell_kept = abs(shell_total_3 - shell_total_stop) < 0.0001
    
    if feeding_reset:
        print(f"    ❌ 投料累计归零了！停止时 {feeding_total_stop:.1f}kg → 续炼开始 {feeding_total_3:.1f}kg")
    elif feeding_kept:
        print(f"    ✅ 投料累计保持不变 ({feeding_total_stop:.1f}kg → {feeding_total_3:.1f}kg)")
    else:
        print(f"    ⚠️ 投料累计异常 ({feeding_total_stop:.1f}kg → {feeding_total_3:.1f}kg)")
    
    if cover_reset:
        print(f"    ❌ 炉盖水累计归零了！停止时 {cover_total_stop:.4f}m³ → 续炼开始 {cover_total_3:.4f}m³")
    elif cover_kept:
        print(f"    ✅ 炉盖水累计保持不变 ({cover_total_stop:.4f}m³ → {cover_total_3:.4f}m³)")
    else:
        print(f"    ⚠️ 炉盖水累计异常 ({cover_total_stop:.4f}m³ → {cover_total_3:.4f}m³)")
    
    if shell_reset:
        print(f"    ❌ 炉皮水累计归零了！停止时 {shell_total_stop:.4f}m³ → 续炼开始 {shell_total_3:.4f}m³")
    elif shell_kept:
        print(f"    ✅ 炉皮水累计保持不变 ({shell_total_stop:.4f}m³ → {shell_total_3:.4f}m³)")
    else:
        print(f"    ⚠️ 炉皮水累计异常 ({shell_total_stop:.4f}m³ → {shell_total_3:.4f}m³)")
    
    # 最终结论
    print("\n" + "=" * 60)
    if feeding_reset or cover_reset or shell_reset:
        print("  ❌ 测试失败：累计值归零了！")
        print("  预期：续炼时累计值应该保持不变，继续累计")
    elif feeding_kept and cover_kept and shell_kept:
        print("  ✅ 测试通过：累计值保持不变，继续累计")
        print("  预期：续炼时累计值应该保持不变，继续累计")
    else:
        print("  ⚠️ 测试部分通过：部分累计值异常")
    print("=" * 60)
    
    # 清理：停止冶炼
    batch_service.stop()
    
    return not (feeding_reset or cover_reset or shell_reset)


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
