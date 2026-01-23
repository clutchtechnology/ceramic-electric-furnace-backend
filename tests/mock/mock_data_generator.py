# ============================================================
# 文件说明: mock_data_generator.py - 电炉模拟PLC原始数据生成器
# ============================================================
# 功能:
# 1. 生成符合PLC DB块结构的16进制原始数据
# 2. 模拟各种传感器的数据变化
# 3. 支持DB32(红外测距/压力/流量)、DB33(电表)、DB30(状态)
# 4. 模拟Modbus RTU料仓重量数据
# ============================================================

import struct
import random
import math
from datetime import datetime
from typing import Dict, Tuple


class MockDataGenerator:
    """电炉模拟PLC原始数据生成器
    
    生成符合PLC DB块结构的原始字节数据
    """
    
    def __init__(self):
        # 基础值 (用于模拟真实电炉场景)
        self._base_values = {
            # 红外测距 - 电极深度 (mm)
            'electrode_depth': [400, 350, 380],  # 3个电极
            
            # 压力传感器 - 冷却水压力 (MPa * 100)
            'water_pressure': [50, 65],  # 炉皮、炉盖
            
            # 流量计 - 冷却水流量 (m³/h * 100)
            'water_flow': [1200, 950],  # 炉皮、炉盖
            
            # 蝶阀开度 (0-100%)
            'valve_opening': [75, 80, 85, 90],
            
            # 电表数据 (DB33)
            'voltage': [380.0, 385.0, 378.0],  # 三相电压 V
            'current': [15.0, 14.5, 16.2],     # 三相电流 A (实际读数，未乘CT变比)
            'power': 6.5,                       # 总功率 kW
            'energy': 1250.0,                   # 累计能耗 kWh
            'power_factor': 0.92,               # 功率因数
            
            # 料仓重量 (kg)
            'hopper_weight': 450,
        }
        
        # 时间累计值
        self._tick = 0
        
        # 能耗累计
        self._energy_accumulator = 1250.0
        
        # 料仓消耗状态
        self._hopper_consuming = False
        self._hopper_consume_rate = 0.0  # kg/s
    
    def tick(self):
        """时间前进一步 (每次轮询调用)"""
        self._tick += 1
        
        # 累计能耗递增
        power_kw = self._base_values['power']
        self._energy_accumulator += power_kw / 3600 * 5  # 5秒增量
        
        # 模拟料仓下料过程 (10% 概率切换)
        if random.random() < 0.1:
            self._hopper_consuming = not self._hopper_consuming
            if self._hopper_consuming:
                self._hopper_consume_rate = random.uniform(0.8, 2.0)
            else:
                self._hopper_consume_rate = 0.0
    
    def _add_noise(self, base: float, noise_range: float = 0.03) -> float:
        """添加随机波动 (默认3%波动)"""
        noise = random.uniform(-noise_range, noise_range)
        return base * (1 + noise)
    
    def _add_sine_wave(self, base: float, amplitude: float = 0.1, period: int = 60) -> float:
        """添加正弦波动 (模拟周期性变化)"""
        wave = math.sin(2 * math.pi * self._tick / period) * amplitude
        return base * (1 + wave)
    
    # ============================================================
    # DB32: 传感器数据块生成 (29 bytes)
    # ============================================================
    
    def generate_db32_infrared_distance(self, electrode_index: int) -> bytes:
        """生成红外测距数据 (4字节)
        
        结构:
        - HIGH (Word, 2B)
        - LOW (Word, 2B)
        距离 = HIGH * 65536 + LOW (mm)
        """
        base_depth = self._base_values['electrode_depth'][electrode_index]
        depth = self._add_sine_wave(base_depth, amplitude=0.05, period=40)
        depth = max(0, depth + random.uniform(-20, 20))
        depth_int = int(depth)
        
        high = depth_int // 65536
        low = depth_int % 65536
        
        return struct.pack('>HH', high, low)
    
    def generate_db32_pressure(self, sensor_index: int) -> bytes:
        """生成压力传感器数据 (2字节)
        
        结构:
        - Pressure (Word, 2B) - 单位: MPa * 100
        """
        base_pressure = self._base_values['water_pressure'][sensor_index]
        pressure = self._add_noise(base_pressure, 0.08)
        pressure = max(0, pressure + random.uniform(-3, 3))
        
        return struct.pack('>H', int(pressure))
    
    def generate_db32_flow(self, sensor_index: int) -> bytes:
        """生成流量计数据 (2字节)
        
        结构:
        - Flow (Word, 2B) - 单位: m³/h * 100
        """
        base_flow = self._base_values['water_flow'][sensor_index]
        flow = self._add_noise(base_flow, 0.1)
        flow = max(0, flow + random.uniform(-50, 50))
        
        return struct.pack('>H', int(flow))
    
    def generate_db32_valve(self, valve_index: int) -> bytes:
        """生成蝶阀数据 (2字节)
        
        结构:
        - Opening (Word, 2B) - 单位: % (0-100)
        """
        base_opening = self._base_values['valve_opening'][valve_index]
        opening = self._add_noise(base_opening, 0.02)
        opening = max(0, min(100, opening))
        
        return struct.pack('>H', int(opening))
    
    def generate_db32_data(self) -> bytes:
        """生成完整的DB32数据块 (29字节)
        
        DB32结构 (config_L3_P2_F2_C4_db32.yaml):
        - LENTH1 (InfraredDistance, 4B, offset=0)
        - LENTH2 (InfraredDistance, 4B, offset=4)
        - LENTH3 (InfraredDistance, 4B, offset=8)
        - WATER_PRESS_1 (PRESSURE, 2B, offset=12)
        - WATER_PRESS_2 (PRESSURE, 2B, offset=14)
        - WATER_FLOW_1 (FLOW_METER, 2B, offset=16)
        - WATER_FLOW_2 (FLOW_METER, 2B, offset=18)
        - MF_1 (ButterFlyValve, 2B, offset=20)
        - MF_2 (ButterFlyValve, 2B, offset=22)
        - MF_3 (ButterFlyValve, 2B, offset=24)
        - MF_4 (ButterFlyValve, 2B, offset=26)
        - MBrly (Word, 2B, offset=28) - 写寄存器，跳过
        总大小: 29字节 (不含 MBrly)
        """
        data = b''
        
        # 3个红外测距 (电极深度)
        data += self.generate_db32_infrared_distance(0)  # LENTH1
        data += self.generate_db32_infrared_distance(1)  # LENTH2
        data += self.generate_db32_infrared_distance(2)  # LENTH3
        
        # 2个压力计
        data += self.generate_db32_pressure(0)  # WATER_PRESS_1
        data += self.generate_db32_pressure(1)  # WATER_PRESS_2
        
        # 2个流量计
        data += self.generate_db32_flow(0)  # WATER_FLOW_1
        data += self.generate_db32_flow(1)  # WATER_FLOW_2
        
        # 4个蝶阀
        data += self.generate_db32_valve(0)  # MF_1
        data += self.generate_db32_valve(1)  # MF_2
        data += self.generate_db32_valve(2)  # MF_3
        data += self.generate_db32_valve(3)  # MF_4
        
        # 注意: 不包含 MBrly (offset=28, 写寄存器)
        
        assert len(data) == 28, f"DB32 size mismatch: {len(data)} != 28"
        return data
    
    # ============================================================
    # DB33: 电表数据块生成 (56 bytes = 14 REAL)
    # ============================================================
    
    def generate_db33_data(self) -> bytes:
        """生成完整的DB33数据块 (56字节)
        
        DB33结构 (config_electricity_db33.yaml):
        14个REAL类型字段 (每个4字节):
        - U_0, U_1, U_2: 三相电压 (V)
        - I_0, I_1, I_2: 三相电流 (A) - 原始读数
        - Pt: 总功率 (kW)
        - Qt: 总无功功率 (kVar)
        - PF: 功率因数
        - Fr: 频率 (Hz)
        - ImpEp: 累计有功电能 (kWh)
        - ImpEq: 累计无功电能 (kVarh)
        - ExpEp: 反向有功电能
        - ExpEq: 反向无功电能
        
        注意: CT变比=20, 实际电流 = I_x * 20
        """
        data = b''
        
        # 三相电压
        for i in range(3):
            voltage = self._add_noise(self._base_values['voltage'][i], 0.02)
            data += struct.pack('>f', voltage)
        
        # 三相电流 (原始读数，未乘CT变比)
        for i in range(3):
            current = self._add_noise(self._base_values['current'][i], 0.05)
            data += struct.pack('>f', current)
        
        # 总功率
        power = self._add_noise(self._base_values['power'], 0.08)
        data += struct.pack('>f', power)
        
        # 总无功功率
        reactive_power = power * 0.3  # 假设无功功率为有功的30%
        data += struct.pack('>f', reactive_power)
        
        # 功率因数
        pf = self._add_noise(self._base_values['power_factor'], 0.01)
        data += struct.pack('>f', pf)
        
        # 频率
        freq = self._add_noise(50.0, 0.002)  # 50Hz ±0.1Hz
        data += struct.pack('>f', freq)
        
        # 累计有功电能
        data += struct.pack('>f', self._energy_accumulator)
        
        # 累计无功电能
        reactive_energy = self._energy_accumulator * 0.3
        data += struct.pack('>f', reactive_energy)
        
        # 反向有功电能 (通常为0)
        data += struct.pack('>f', 0.0)
        
        # 反向无功电能 (通常为0)
        data += struct.pack('>f', 0.0)
        
        assert len(data) == 56, f"DB33 size mismatch: {len(data)} != 56"
        return data
    
    # ============================================================
    # DB30: 通信状态块生成 (40 bytes)
    # ============================================================
    
    def generate_db30_data(self) -> bytes:
        """生成完整的DB30数据块 (40字节)
        
        DB30结构 (status_L3_P2_F2_C4_db30.yaml):
        10个设备的通信状态，每个设备4字节:
        - Addr (Word, 2B): Modbus地址
        - TxOK (Bool, 1bit): 发送成功
        - RxOK (Bool, 1bit): 接收成功
        - CommOK (Bool, 1bit): 通信正常
        - (其他位保留)
        - Byte3 (Byte, 1B): 保留
        """
        data = b''
        
        # 10个设备，模拟通信状态
        for i in range(10):
            addr = 1 + i  # Modbus地址 1-10
            
            # 模拟通信状态 (95%概率正常)
            is_ok = random.random() < 0.95
            status_byte = 0x07 if is_ok else 0x00  # Bit0-2: TxOK, RxOK, CommOK
            
            data += struct.pack('>H', addr)       # Addr
            data += struct.pack('B', status_byte) # Status
            data += struct.pack('B', 0)           # Reserved
        
        assert len(data) == 40, f"DB30 size mismatch: {len(data)} != 40"
        return data
    
    # ============================================================
    # Modbus RTU: 料仓重量生成
    # ============================================================
    
    def generate_hopper_weight(self) -> int:
        """生成料仓净重 (kg)
        
        返回:
            净重整数 (kg)
        """
        base_weight = self._base_values['hopper_weight']
        
        # 如果正在下料，递减重量
        if self._hopper_consuming:
            base_weight -= self._hopper_consume_rate * 5  # 5秒增量
            base_weight = max(0, base_weight)
            self._base_values['hopper_weight'] = base_weight
        
        # 添加噪声
        weight = self._add_noise(base_weight, 0.005)
        weight = max(0, weight + random.uniform(-2, 2))
        
        return int(weight)
    
    # ============================================================
    # 主生成函数
    # ============================================================
    
    def generate_all_db_data(self) -> Dict[int, bytes]:
        """生成所有DB块的模拟数据
        
        返回:
            {db_number: raw_bytes}
        """
        self.tick()
        
        return {
            30: self.generate_db30_data(),  # 通信状态
            32: self.generate_db32_data(),  # 传感器数据
            33: self.generate_db33_data(),  # 电表数据
        }
    
    def get_hopper_weight(self) -> int:
        """获取当前料仓重量 (用于Modbus RTU模拟)"""
        return self.generate_hopper_weight()


# ============================================================
# 测试代码
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("电炉 Mock 数据生成器测试")
    print("=" * 60)
    
    generator = MockDataGenerator()
    
    # 生成5次数据
    for i in range(5):
        print(f"\n第 {i+1} 次生成:")
        
        all_data = generator.generate_all_db_data()
        
        print(f"  DB30 (状态): {len(all_data[30])} bytes")
        print(f"  DB32 (传感器): {len(all_data[32])} bytes")
        print(f"  DB33 (电表): {len(all_data[33])} bytes")
        print(f"  料仓重量: {generator.get_hopper_weight()} kg")
        
        # 打印前8字节（十六进制）
        print(f"  DB32前8字节: {all_data[32][:8].hex()}")
