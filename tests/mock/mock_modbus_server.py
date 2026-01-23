#!/usr/bin/env python3
# ============================================================
# 文件说明: mock_modbus_server.py - 模拟Modbus RTU料仓重量服务器
# ============================================================
# 功能:
# 1. 模拟真实的Modbus RTU设备（料仓称重仪表）
# 2. 提供虚拟串口服务，可被正式轮询代码读取
# 3. 使用 pymodbus 库作为服务器
# 4. 动态生成料仓重量数据
#
# 使用场景:
#   测试真实Modbus RTU读取代码
#   验证串口通信逻辑
#
# 使用方法:
#   1. 安装虚拟串口工具:
#      - Windows: com0com (创建虚拟串口对 COM10<->COM11)
#      - Linux: socat (创建虚拟串口对 /tmp/vcom0 <-> /tmp/vcom1)
#   2. 启动此服务: python tests/mock/mock_modbus_server.py --port COM10
#   3. 修改 config.py: modbus_port = "COM11"
#   4. 启动正式后端: python main.py
#
# 停止方法:
#   Ctrl+C
# ============================================================

import sys
import os
import time
import signal
import argparse
from typing import Optional

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

try:
    from pymodbus.server import StartSerialServer
    from pymodbus.device import ModbusDeviceIdentification
    from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
    PYMODBUS_AVAILABLE = True
except ImportError:
    PYMODBUS_AVAILABLE = False
    print("❌ pymodbus 未安装，无法启动Mock Modbus服务器")
    print("   安装方法: pip install pymodbus")
    sys.exit(1)

from tests.mock.mock_data_generator import MockDataGenerator

# ============================================================
# 配置
# ============================================================
DEFAULT_PORT = "COM10"  # Windows虚拟串口
DEFAULT_BAUDRATE = 19200
DEFAULT_SLAVE_ID = 1

UPDATE_INTERVAL = 5  # 数据更新间隔 (秒)

# Modbus 保持寄存器地址 (根据称重仪表手册)
# 通常料仓重量存储在 40001-40002 (2个寄存器，32位整数)
WEIGHT_REGISTER_START = 0  # Modbus地址 40001 (0-based)
WEIGHT_REGISTER_COUNT = 2  # 2个寄存器 (32位)

# ============================================================
# 全局变量
# ============================================================
_generator: Optional[MockDataGenerator] = None
_datastore: Optional[ModbusSlaveContext] = None
_is_running = True


def signal_handler(sig, frame):
    """处理Ctrl+C信号"""
    global _is_running
    print("\n⏹️  收到停止信号，正在退出...")
    _is_running = False
    sys.exit(0)


def update_weight_data():
    """更新重量数据到Modbus寄存器"""
    global _generator, _datastore
    
    # 生成新的重量值
    weight = _generator.get_hopper_weight()
    
    # 将重量转换为2个16位寄存器 (32位整数)
    # 高16位在前，低16位在后 (Big Endian)
    high_word = (weight >> 16) & 0xFFFF
    low_word = weight & 0xFFFF
    
    # 写入寄存器
    _datastore.setValues(3, WEIGHT_REGISTER_START, [high_word, low_word])
    
    # 打印更新
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] 重量已更新: {weight} kg (寄存器: 0x{high_word:04X} 0x{low_word:04X})")


def updating_writer(context):
    """后台线程，定期更新数据"""
    global _is_running
    
    print("🔄 数据更新线程启动")
    
    while _is_running:
        try:
            update_weight_data()
        except Exception as e:
            print(f"❌ 数据更新错误: {e}")
        
        time.sleep(UPDATE_INTERVAL)
    
    print("🔄 数据更新线程已停止")


def run_mock_modbus_server(port: str, baudrate: int, slave_id: int):
    """启动模拟Modbus RTU服务器"""
    global _generator, _datastore
    
    print("=" * 60)
    print("🚀 电炉 Mock Modbus RTU 服务器启动")
    print("=" * 60)
    print(f"📡 串口: {port}")
    print(f"📊 波特率: {baudrate}")
    print(f"🆔 从站ID: {slave_id}")
    print(f"📦 寄存器: 40001-40002 (料仓重量, kg)")
    print(f"🔄 数据更新: 每 {UPDATE_INTERVAL} 秒")
    print("=" * 60)
    print("按 Ctrl+C 停止服务")
    print("=" * 60)
    
    # 初始化数据生成器
    _generator = MockDataGenerator()
    
    # 创建Modbus数据存储
    # 保持寄存器 (Holding Registers): 功能码03/16
    hr_block = ModbusSequentialDataBlock(0, [0] * 100)
    
    # 初始化重量值
    weight = _generator.get_hopper_weight()
    high_word = (weight >> 16) & 0xFFFF
    low_word = weight & 0xFFFF
    hr_block.setValues(WEIGHT_REGISTER_START, [high_word, low_word])
    print(f"✅ 初始重量: {weight} kg")
    
    # 创建从站上下文
    _datastore = ModbusSlaveContext(
        di=ModbusSequentialDataBlock(0, [0] * 100),  # Discrete Inputs
        co=ModbusSequentialDataBlock(0, [0] * 100),  # Coils
        hr=hr_block,  # Holding Registers
        ir=ModbusSequentialDataBlock(0, [0] * 100),  # Input Registers
    )
    
    # 创建服务器上下文
    context = ModbusServerContext(slaves={slave_id: _datastore}, single=False)
    
    # 设备标识
    identity = ModbusDeviceIdentification()
    identity.VendorName = 'Mock Weighing Instrument'
    identity.ProductCode = 'MWI-1000'
    identity.VendorUrl = 'http://localhost'
    identity.ProductName = 'Mock Weighing Instrument for Testing'
    identity.ModelName = 'Mock Modbus RTU'
    identity.MajorMinorRevision = '1.0.0'
    
    print(f"\n🎯 服务器监听中: {port} ({baudrate} bps)")
    
    # 启动服务器（阻塞）
    try:
        StartSerialServer(
            context=context,
            identity=identity,
            port=port,
            baudrate=baudrate,
            bytesize=8,
            parity='E',  # Even parity
            stopbits=1,
            timeout=1,
            # 后台更新器
            custom_functions=[],
        )
    except KeyboardInterrupt:
        print("\n⏹️  服务器已停止")
    except Exception as e:
        print(f"\n❌ 服务器错误: {e}")
        import traceback
        traceback.print_exc()


def main():
    """主入口"""
    parser = argparse.ArgumentParser(description='Mock Modbus RTU 料仓重量服务器')
    parser.add_argument('--port', type=str, default=DEFAULT_PORT, help=f'串口号 (默认: {DEFAULT_PORT})')
    parser.add_argument('--baudrate', type=int, default=DEFAULT_BAUDRATE, help=f'波特率 (默认: {DEFAULT_BAUDRATE})')
    parser.add_argument('--slave-id', type=int, default=DEFAULT_SLAVE_ID, help=f'从站ID (默认: {DEFAULT_SLAVE_ID})')
    
    args = parser.parse_args()
    
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 启动服务器
    run_mock_modbus_server(args.port, args.baudrate, args.slave_id)


if __name__ == "__main__":
    main()
