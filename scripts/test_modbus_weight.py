# ============================================================
# 文件说明: test_modbus_weight.py - Modbus RTU 料仓重量测试脚本
# ============================================================
# 用法:
#   cd D:\furnace-backend
#   venv\Scripts\python scripts\test_modbus_weight.py
# ============================================================

import sys
sys.path.insert(0, '.')

from app.tools.operation_modbus_weight_reader import (
    read_hopper_weight,
    build_read_request,
    parse_response_hex
)

print("=" * 60)
print("Modbus RTU 料仓重量测试")
print("=" * 60)

# 1. 测试请求报文构建
print("\n1. 测试请求报文构建:")
req = build_read_request(slave_addr=1, start_reg=2, reg_count=2)
print(f"   生成报文: {req.hex(' ').upper()}")
print(f"   期望值:   01 03 00 02 00 02 65 CB")
if req.hex(' ').upper() == "01 03 00 02 00 02 65 CB":
    print("   [PASS] 请求报文生成正确")
else:
    print("   [FAIL] 请求报文生成错误")

# 2. 测试响应解析
print("\n2. 测试响应解析:")
test_response = "01 03 04 00 00 01 22 7B BA"
success, weight, error = parse_response_hex(test_response)
print(f"   输入: {test_response}")
print(f"   解析: weight={weight} kg, success={success}")
if weight == 290:
    print("   [PASS] 响应解析正确 (290 kg)")
else:
    print(f"   [FAIL] 响应解析错误 (期望 290 kg, 实际 {weight} kg)")

# 3. 测试实际 COM1 读取
print("\n3. 测试实际 COM1 读取:")
print("   正在连接 COM1...")
result = read_hopper_weight(port='COM1', baudrate=19200, timeout=2.0)

print(f"   成功: {result['success']}")
print(f"   净重: {result['weight']} kg" if result['success'] else f"   净重: N/A")
print(f"   单位: {result['unit']}")
if result['raw_response']:
    print(f"   原始: {result['raw_response'].hex(' ').upper()}")
else:
    print(f"   原始: None")
    
if result['error']:
    print(f"   错误: {result['error']}")
    print("\n   [FAIL] 串口读取失败")
else:
    print("   [PASS] 串口读取成功")

# 4. 总结
print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)

if result['success']:
    print(f"\n料仓当前净重: {result['weight']} kg")
    print("\n[提示] 如果重量异常，请检查:")
    print("  1. 传感器是否正确连接到 COM1")
    print("  2. 传感器从站地址是否为 1")
    print("  3. 波特率是否为 19200")
    print("  4. 串口参数: 8E1 (8位数据, 偶校验, 1位停止)")
else:
    print("\n[故障排查]")
    print("  1. 检查 COM1 是否被其他程序占用")
    print("  2. 确认设备管理器中 COM1 存在且正常")
    print("  3. 检查串口线是否连接正确")
    print("  4. 验证传感器供电是否正常")
    print("  5. 尝试: python scripts/read_hopper_weight.py COM1")
