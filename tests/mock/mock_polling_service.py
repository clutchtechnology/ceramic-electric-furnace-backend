#!/usr/bin/env python3
# ============================================================
# 文件说明: mock_polling_service.py - 电炉模拟轮询服务
# ============================================================
# 功能:
# 1. 模拟PLC轮询，生成符合DB块结构的原始数据
# 2. 使用与正式代码相同的解析器和转换器
# 3. 将数据写入InfluxDB
# 4. 每5秒轮询一次
# 5. 模拟Modbus RTU料仓重量读取
#
# 使用方法:
#   python tests/mock/mock_polling_service.py
#
# 停止方法:
#   Ctrl+C
# ============================================================

import sys
import os
import asyncio
import signal
from datetime import datetime
from typing import Dict, Any

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from tests.mock.mock_data_generator import MockDataGenerator
from config import get_settings
from app.core.influxdb import write_point
from app.plc.parser_modbus import ModbusDataParser
from app.plc.parser_status import ModbusStatusParser
from app.plc.parser_config_db33 import ConfigDrivenDB33Parser
from app.tools.converter_furnace import FurnaceConverter

settings = get_settings()

# ============================================================
# 配置
# ============================================================
POLL_INTERVAL = 5  # 轮询间隔 (秒)

# 解析器实例
_modbus_parser = ModbusDataParser()
_status_parser = ModbusStatusParser()
_db33_parser = ConfigDrivenDB33Parser()
_furnace_converter = FurnaceConverter()

# 运行状态
_is_running = True


def signal_handler(sig, frame):
    """处理Ctrl+C信号"""
    global _is_running
    print("\n⏹️  收到停止信号，正在退出...")
    _is_running = False


def write_modbus_data_to_influx(parsed_data: Dict[str, Any], timestamp: datetime):
    """写入DB32传感器数据到InfluxDB
    
    Args:
        parsed_data: 解析后的数据 (包含 electrode_depths, cooling_pressures, cooling_flows, valve_openings)
        timestamp: 时间戳
    """
    # 1. 红外测距 (电极深度)
    for name, value_dict in parsed_data.get('electrode_depths', {}).items():
        write_point(
            measurement="sensor_data",
            tags={
                "device_id": "furnace_1",
                "device_type": "electric_furnace",
                "module_type": "infrared_distance",
                "sensor_name": name,
            },
            fields={
                "distance": value_dict.get('distance', 0),
                "high": value_dict.get('high', 0),
                "low": value_dict.get('low', 0),
            },
            timestamp=timestamp
        )
    
    # 2. 压力传感器
    for name, value_dict in parsed_data.get('cooling_pressures', {}).items():
        write_point(
            measurement="sensor_data",
            tags={
                "device_id": "furnace_1",
                "device_type": "electric_furnace",
                "module_type": "pressure",
                "sensor_name": name,
            },
            fields={
                "pressure": value_dict.get('pressure', 0),
                "raw": value_dict.get('raw', 0),
            },
            timestamp=timestamp
        )
    
    # 3. 流量计
    for name, value_dict in parsed_data.get('cooling_flows', {}).items():
        write_point(
            measurement="sensor_data",
            tags={
                "device_id": "furnace_1",
                "device_type": "electric_furnace",
                "module_type": "flow_meter",
                "sensor_name": name,
            },
            fields={
                "flow": value_dict.get('flow', 0),
                "raw": value_dict.get('raw', 0),
            },
            timestamp=timestamp
        )
    
    # 4. 蝶阀
    for name, value_dict in parsed_data.get('valve_openings', {}).items():
        write_point(
            measurement="sensor_data",
            tags={
                "device_id": "furnace_1",
                "device_type": "electric_furnace",
                "module_type": "butterfly_valve",
                "sensor_name": name,
            },
            fields={
                "opening": value_dict.get('opening', 0),
            },
            timestamp=timestamp
        )


def write_electricity_data_to_influx(raw_data: Dict[str, float], converted_data: Dict[str, float], timestamp: datetime):
    """写入DB33电表数据到InfluxDB
    
    Args:
        raw_data: 原始读数
        converted_data: 转换后数据 (乘以CT/PT变比)
        timestamp: 时间戳
    """
    # 合并所有字段
    all_fields = {**converted_data}
    all_fields['ct_ratio'] = 20  # 记录变比
    
    write_point(
        measurement="sensor_data",
        tags={
            "device_id": "furnace_1",
            "device_type": "electric_furnace",
            "module_type": "electricity_meter",
            "sensor_name": "main_meter",
        },
        fields=all_fields,
        timestamp=timestamp
    )


def write_weight_data_to_influx(weight: int, timestamp: datetime):
    """写入料仓重量数据到InfluxDB
    
    Args:
        weight: 净重 (kg)
        timestamp: 时间戳
    """
    write_point(
        measurement="sensor_data",
        tags={
            "device_id": "hopper_1",
            "device_type": "hopper",
            "module_type": "weight",
            "sensor_name": "net_weight",
        },
        fields={
            "weight": weight,
        },
        timestamp=timestamp
    )


async def poll_mock_data():
    """模拟轮询主循环"""
    global _is_running
    
    print("=" * 60)
    print("🚀 电炉模拟轮询服务启动")
    print("=" * 60)
    print(f"📊 轮询间隔: {POLL_INTERVAL}秒")
    print(f"📦 DB块: DB30(状态), DB32(传感器), DB33(电表)")
    print(f"🔗 InfluxDB: {settings.influx_url}")
    print(f"📁 Bucket: {settings.influx_bucket}")
    print("=" * 60)
    print("按 Ctrl+C 停止服务")
    print("=" * 60)
    
    # 初始化数据生成器
    generator = MockDataGenerator()
    
    poll_count = 0
    
    while _is_running:
        try:
            poll_count += 1
            timestamp = datetime.now()
            
            print(f"\n[{timestamp.strftime('%H:%M:%S')}] 第 {poll_count} 次轮询...")
            
            # 生成所有DB块的模拟数据
            all_db_data = generator.generate_all_db_data()
            
            # =============== 处理 DB32 (传感器数据) ===============
            db32_raw = all_db_data[32]
            db32_parsed = _modbus_parser.parse(db32_raw)
            write_modbus_data_to_influx(db32_parsed, timestamp)
            print(f"  ✅ DB32 (传感器): 已写入 - 电极深度, 压力, 流量, 蝶阀")
            
            # =============== 处理 DB33 (电表数据) ===============
            db33_raw = all_db_data[33]
            db33_parsed = _db33_parser.parse(db33_raw)
            raw_data = db33_parsed['raw']
            converted_data = _furnace_converter.convert_electricity(raw_data)
            write_electricity_data_to_influx(raw_data, converted_data, timestamp)
            print(f"  ✅ DB33 (电表): Pt={converted_data['Pt']:.2f}kW, "
                  f"I_0={converted_data['I_0']:.1f}A (CT=20)")
            
            # =============== 处理 DB30 (状态数据 - 仅打印不写入) ===============
            db30_raw = all_db_data[30]
            db30_parsed = _status_parser.parse(db30_raw)
            online_count = sum(1 for dev in db30_parsed['devices'] if dev['comm_ok'])
            print(f"  ℹ️  DB30 (状态): {online_count}/10 设备在线")
            
            # =============== 处理 Modbus RTU (料仓重量) ===============
            hopper_weight = generator.get_hopper_weight()
            write_weight_data_to_influx(hopper_weight, timestamp)
            print(f"  ✅ 料仓重量: {hopper_weight} kg")
            
            print(f"  📊 轮询统计: 共 {poll_count} 次")
            
        except Exception as e:
            print(f"  ❌ 轮询错误: {e}")
            import traceback
            traceback.print_exc()
        
        # 等待下次轮询
        await asyncio.sleep(POLL_INTERVAL)
    
    print("\n✅ 模拟轮询服务已停止")


def main():
    """主入口"""
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 运行异步轮询
    try:
        asyncio.run(poll_mock_data())
    except KeyboardInterrupt:
        print("\n⏹️  服务已停止")


if __name__ == "__main__":
    main()
