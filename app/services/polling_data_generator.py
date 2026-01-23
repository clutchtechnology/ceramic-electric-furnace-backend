# ============================================================
# 文件说明: polling_data_generator.py - Mock数据生成器
# ============================================================
# 功能:
#   为开发和测试提供 Mock 数据生成
#   包含: DB1/DB30/DB32/DB41 等所有数据块的 Mock 生成
# ============================================================

import random
import struct
from typing import Dict, Any


def generate_mock_db32_data() -> bytes:
    """生成 Mock DB32 数据 (21字节)
    
    数据结构 (根据 config_L3_P2_F2_C4_db32.yaml):
    - LENTH1-3: 红外测距 UDInt (3 x 4 bytes = 12 bytes) offset 0-11
    - WATER_PRESS_1-2: 压力 Int (2 x 2 bytes = 4 bytes) offset 12-15
    - WATER_FLOW_1-2: 流量 Int (2 x 2 bytes = 4 bytes) offset 16-19
    - ValveStatus: 蝶阀状态监测 Byte (1 byte) offset 20
    """
    data = bytearray(21)
    
    # LENTH1-3: 红外测距 UDInt (模拟电极深度 100-500mm)
    for i in range(3):
        offset = i * 4
        distance = random.randint(100, 500)
        # UDInt: 无符号32位整数，大端序
        struct.pack_into('>I', data, offset, distance)
    
    # WATER_PRESS_1-2: 压力 Int (模拟 0.3-0.8 MPa, 原始值 30-80)
    struct.pack_into('>h', data, 12, random.randint(30, 80))
    struct.pack_into('>h', data, 14, random.randint(30, 80))
    
    # WATER_FLOW_1-2: 流量 Int (模拟 5-15 m³/h, 原始值 500-1500)
    struct.pack_into('>h', data, 16, random.randint(500, 1500))
    struct.pack_into('>h', data, 18, random.randint(500, 1500))
    
    # ValveStatus: 蝶阀状态监测 Byte (随机生成一些蝶阀开启/关闭状态)
    # 每个bit对应一个蝶阀: bit0=蝶阀1, bit1=蝶阀2, ..., bit7=蝶阀8
    valve_status = random.randint(0, 255)  # 随机状态
    data[20] = valve_status
    
    return bytes(data)


def generate_mock_db1_data() -> bytes:
    """生成 Mock DB1 弧流弧压数据 (182字节)
    
    数据结构（根据实际PLC配置）:
    - offset 0-7: 电机输出 (4 x Int)
    - offset 8-9: U相弧流中间值 (不存储)
    - offset 10-11: U相弧流 (INT, A)
    - offset 12-13: U相弧压 (INT, V)
    - offset 14-15: V相弧流中间值 (不存储)
    - offset 16-17: V相弧流 (INT, A)
    - offset 18-19: V相弧压 (INT, V)
    - offset 20-21: W相弧流中间值 (不存储)
    - offset 22-23: W相弧流 (INT, A)
    - offset 24-25: W相弧压 (INT, V)
    - offset 26-27: 弧流给定中间值 (不存储)
    - offset 28-29: 弧流设定值 (INT, A)
    - offset 30-63: Vw变量
    - offset 64-67: 死区上下限
      - 64-65: 死区下限 (INT, A)
      - 66-67: 死区上限 (INT, A)
    - offset 68-181: 其他变量
    """
    data = bytearray(182)
    
    # ========================================
    # 电机输出 (offset 0-7, 4 x Int)
    # ========================================
    for i in range(4):
        motor_value = random.randint(0, 100)  # 0-100%
        struct.pack_into('>h', data, i * 2, motor_value)
    
    # ========================================
    # UVW三相弧流弧压 + 设定值 (跳过中间值)
    # ========================================
    ARC_CURRENT_TARGET = 5978  # 目标弧流 5978 A
    ARC_VOLTAGE_TARGET = 80    # 目标弧压 80 V
    
    # U相弧流中间值 (offset 8-9, 不使用)
    struct.pack_into('>h', data, 8, random.randint(5000, 6000))
    
    # U相弧流 (offset 10-11)
    arc_current_U = int(ARC_CURRENT_TARGET + random.uniform(-598, 598))
    struct.pack_into('>h', data, 10, arc_current_U)
    
    # U相弧压 (offset 12-13)
    arc_voltage_U = int(ARC_VOLTAGE_TARGET + random.uniform(-10, 10))
    struct.pack_into('>h', data, 12, arc_voltage_U)
    
    # V相弧流中间值 (offset 14-15, 不使用)
    struct.pack_into('>h', data, 14, random.randint(5000, 6000))
    
    # V相弧流 (offset 16-17)
    arc_current_V = int(ARC_CURRENT_TARGET + random.uniform(-598, 598))
    struct.pack_into('>h', data, 16, arc_current_V)
    
    # V相弧压 (offset 18-19)
    arc_voltage_V = int(ARC_VOLTAGE_TARGET + random.uniform(-10, 10))
    struct.pack_into('>h', data, 18, arc_voltage_V)
    
    # W相弧流中间值 (offset 20-21, 不使用)
    struct.pack_into('>h', data, 20, random.randint(5000, 6000))
    
    # W相弧流 (offset 22-23)
    arc_current_W = int(ARC_CURRENT_TARGET + random.uniform(-598, 598))
    struct.pack_into('>h', data, 22, arc_current_W)
    
    # W相弧压 (offset 24-25)
    arc_voltage_W = int(ARC_VOLTAGE_TARGET + random.uniform(-10, 10))
    struct.pack_into('>h', data, 24, arc_voltage_W)
    
    # 弧流给定中间值 (offset 26-27, 不使用)
    struct.pack_into('>h', data, 26, random.randint(5000, 6000))
    
    # 弧流设定值 (offset 28-29)
    arc_setpoint = ARC_CURRENT_TARGET
    struct.pack_into('>h', data, 28, arc_setpoint)
    
    # ========================================
    # Vw变量 (offset 30-63, 填充随机值)
    # ========================================
    for i in range(30, 64, 2):
        struct.pack_into('>h', data, i, random.randint(0, 1000))
    
    # ========================================
    # 死区上下限 (offset 64-67)
    # ========================================
    deadzone_lower = int(ARC_CURRENT_TARGET * 0.9)  # 5380 A (下限)
    deadzone_upper = int(ARC_CURRENT_TARGET * 1.1)  # 6576 A (上限)
    
    struct.pack_into('>h', data, 64, deadzone_lower)  # offset 64: 下限
    struct.pack_into('>h', data, 66, deadzone_upper)  # offset 66: 上限
    
    # ========================================
    # 其他变量 (offset 68-181, 填充随机值)
    # ========================================
    for i in range(68, 182, 2):
        struct.pack_into('>h', data, i, random.randint(0, 100))
    
    return bytes(data)


def generate_mock_db30_data() -> bytes:
    """生成 Mock DB30 状态数据 (40字节)
    
    10个状态模块，每个4字节:
    - Byte 0: Done/Error/Running 位状态
    - Byte 1-3: Reserved / Status
    """
    data = bytearray(40)
    
    # 10个状态模块，每个4字节
    for i in range(10):
        offset = i * 4
        # 90% 概率正常 (Done=true, Error=false, Status=0)
        if random.random() < 0.9:
            data[offset] = 0x01  # Done=true
            data[offset + 1] = 0x00
            data[offset + 2] = 0x00
            data[offset + 3] = 0x00
        else:
            # 10% 概率异常
            data[offset] = 0x04  # Error=true
            data[offset + 1] = 0x00
            data[offset + 2] = 0x80
            data[offset + 3] = 0x01  # Status=0x8001
    
    return bytes(data)


def generate_mock_db41_data() -> bytes:
    """生成 Mock DB41 数据状态 (28字节)
    
    7个设备的数据状态 (每设备 4 字节):
    - LENTH1-3: 测距传感器 @ 0, 4, 8
    - WATER_1-2: 流量计 @ 12, 16
    - PRESS_1-2: 压力计 @ 20, 24
    
    每个模块结构 (4字节对齐):
    - Error: Bool @ offset+0
    - (保留) @ offset+1
    - Status: Word @ offset+2
    """
    data = bytearray(28)  # 7 设备 × 4 字节 = 28 字节
    
    # LENTH1-3 @ 0, 4, 8
    for offset in [0, 4, 8]:
        if random.random() < 0.92:
            data[offset] = 0x00  # Error = false
            struct.pack_into('>H', data, offset + 2, 0x0000)  # Status = 0 (正常)
        else:
            data[offset] = 0x01  # Error = true
            struct.pack_into('>H', data, offset + 2, 0x8001)  # Status 错误码
    
    # WATER_1-2 @ 12, 16
    for offset in [12, 16]:
        if random.random() < 0.92:
            data[offset] = 0x00
            struct.pack_into('>H', data, offset + 2, 0x0000)
        else:
            data[offset] = 0x01
            struct.pack_into('>H', data, offset + 2, 0x8002)
    
    # PRESS_1-2 @ 20, 24 (修正偏移量)
    for offset in [20, 24]:
        if random.random() < 0.92:
            data[offset] = 0x00
            struct.pack_into('>H', data, offset + 2, 0x0000)
        else:
            data[offset] = 0x01
            struct.pack_into('>H', data, offset + 2, 0x8003)
    
    return bytes(data)


def generate_mock_weight_data() -> Dict[str, Any]:
    """生成 Mock 料仓重量数据
    
    Returns:
        与 read_hopper_weight() 相同格式的结果
    """
    from app.tools.operation_modbus_weight_reader import mock_read_weight
    
    # 使用模块提供的 mock 函数，模拟 200-500kg 的净重
    weight = random.randint(200, 500)
    return mock_read_weight(weight=weight)
