# ============================================================
# 文件说明: polling_service.py - 数据轮询服务
# ============================================================
# 功能:
#   1. 定时轮询 PLC DB32 数据块 (传感器数据)
#   2. 定时轮询 PLC DB30 数据块 (通信状态)
#   3. 数据解析后存入 InfluxDB (DB32) 和内存缓存 (DB30)
#   4. 支持 Mock 模式和真实 PLC 模式
# ============================================================

import asyncio
import random
import threading
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from collections import deque

from config import get_settings
from app.core.influxdb import write_point, write_points_batch, build_point
from app.plc.plc_manager import get_plc_manager, SNAP7_AVAILABLE
from app.plc.parser_modbus import ModbusDataParser
from app.plc.parser_status import ModbusStatusParser
from app.tools.converter_furnace import FurnaceConverter

settings = get_settings()

# ============================================================
# 轮询任务控制
# ============================================================
_polling_task: Optional[asyncio.Task] = None
_running = False

# ============================================================
# 解析器与转换器实例
# ============================================================
_modbus_parser: Optional[ModbusDataParser] = None
_status_parser: Optional[ModbusStatusParser] = None
_furnace_converter: Optional[FurnaceConverter] = None

# ============================================================
# 内存缓存 (供 API 直接读取)
# ============================================================
_data_lock = threading.Lock()

# 最新传感器数据缓存 (DB32)
_latest_modbus_data: Dict[str, Any] = {}
_latest_modbus_timestamp: Optional[datetime] = None

# 最新通信状态缓存 (DB30)
_latest_status_data: Dict[str, Any] = {}
_latest_status_timestamp: Optional[datetime] = None

# ============================================================
# 批量写入缓存
# ============================================================
_point_buffer: deque = deque(maxlen=500)
_buffer_count = 0
_batch_size = 10  # 10次轮询后批量写入

# ============================================================
# 统计信息
# ============================================================
_stats = {
    "total_polls": 0,
    "successful_writes": 0,
    "failed_writes": 0,
    "last_poll_time": None,
}


def _init_parsers():
    """初始化解析器"""
    global _modbus_parser, _status_parser, _furnace_converter
    
    if _modbus_parser is None:
        try:
            _modbus_parser = ModbusDataParser()
            print("✅ DB32 传感器数据解析器已初始化")
        except Exception as e:
            print(f"❌ DB32 解析器初始化失败: {e}")
    
    if _status_parser is None:
        try:
            _status_parser = ModbusStatusParser()
            print("✅ DB30 状态解析器已初始化")
        except Exception as e:
            print(f"❌ DB30 解析器初始化失败: {e}")
            
    if _furnace_converter is None:
        _furnace_converter = FurnaceConverter()
        print("✅ 电炉数据转换器已初始化")


async def start_polling():
    """启动轮询服务"""
    global _polling_task, _running
    
    if _running:
        print("轮询服务已在运行")
        return
    
    _init_parsers()
    _running = True
    
    if settings.enable_mock_polling:
        print(f"🔄 启动 Mock 轮询服务 (间隔: {settings.polling_interval}s)")
        _polling_task = asyncio.create_task(_mock_polling_loop())
    elif settings.enable_polling:
        print(f"🔄 启动 PLC 轮询服务 (间隔: {settings.polling_interval}s)")
        _polling_task = asyncio.create_task(_plc_polling_loop())
    else:
        print("⚠️ 轮询服务未启用 (enable_polling=False, enable_mock_polling=False)")


async def stop_polling():
    """停止轮询服务"""
    global _polling_task, _running
    
    _running = False
    
    if _polling_task:
        _polling_task.cancel()
        try:
            await _polling_task
        except asyncio.CancelledError:
            pass
        _polling_task = None
    
    print("轮询服务已停止")


# ============================================================
# Mock 模式轮询
# ============================================================
async def _mock_polling_loop():
    """Mock 模式轮询循环"""
    global _buffer_count
    poll_count = 0
    
    while _running:
        try:
            poll_count += 1
            _stats["total_polls"] = poll_count
            _stats["last_poll_time"] = datetime.now().isoformat()
            
            # 生成 Mock DB32 数据
            mock_db32 = _generate_mock_db32_data()
            _process_modbus_data(mock_db32)
            
            # 生成 Mock DB30 状态数据
            mock_db30 = _generate_mock_db30_data()
            _process_status_data(mock_db30)
            
            # 批量写入检查
            _buffer_count += 1
            if _buffer_count >= _batch_size:
                await _flush_buffer()
                _buffer_count = 0
            
            if poll_count % 12 == 0:
                print(f"📊 Mock轮询 #{poll_count} - 数据已更新")
            
            await asyncio.sleep(settings.polling_interval)
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"❌ Mock轮询异常: {e}")
            await asyncio.sleep(5)


def _generate_mock_db32_data() -> bytes:
    """生成 Mock DB32 数据 (29字节)"""
    import struct
    
    data = bytearray(29)
    
    # LENTH1-3: 红外测距 (模拟电极深度 100-500mm)
    for i in range(3):
        offset = i * 4
        distance = random.randint(100, 500)
        high = (distance >> 16) & 0xFFFF
        low = distance & 0xFFFF
        struct.pack_into('>H', data, offset, high)
        struct.pack_into('>H', data, offset + 2, low)
    
    # WATER_PRESS_1-2: 压力 (模拟 0.3-0.8 MPa, 原始值 30-80)
    struct.pack_into('>H', data, 12, random.randint(30, 80))
    struct.pack_into('>H', data, 14, random.randint(30, 80))
    
    # WATER_FLOW_1-2: 流量 (模拟 5-15 m³/h, 原始值 500-1500)
    struct.pack_into('>H', data, 16, random.randint(500, 1500))
    struct.pack_into('>H', data, 18, random.randint(500, 1500))
    
    # Ctrl_1-4: 蝶阀状态 (随机)
    for i in range(4):
        offset = 20 + i * 2
        status = random.choice([0x01, 0x02, 0x00])  # OPEN, CLOSE, 或无状态
        struct.pack_into('>H', data, offset, status)
    
    # MBrly: 写入寄存器 (不需要)
    data[28] = 0x00
    
    return bytes(data)


def _generate_mock_db30_data() -> bytes:
    """生成 Mock DB30 状态数据 (40字节)"""
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


# ============================================================
# 真实 PLC 轮询
# ============================================================
async def _plc_polling_loop():
    """真实 PLC 轮询循环"""
    global _buffer_count
    poll_count = 0
    plc = get_plc_manager()
    
    # 获取 DB 配置
    db32_number = _modbus_parser.get_db_number()
    db32_size = _modbus_parser.get_total_size()
    db30_number = _status_parser.get_db_number()
    db30_size = _status_parser.get_total_size()
    
    while _running:
        try:
            poll_count += 1
            _stats["total_polls"] = poll_count
            _stats["last_poll_time"] = datetime.now().isoformat()
            
            # 读取 DB32 (传感器数据)
            db32_data, err = plc.read_db(db32_number, 0, db32_size)
            if db32_data:
                _process_modbus_data(db32_data)
            else:
                print(f"⚠️ 读取 DB{db32_number} 失败: {err}")
            
            # 读取 DB30 (通信状态)
            db30_data, err = plc.read_db(db30_number, 0, db30_size)
            if db30_data:
                _process_status_data(db30_data)
            else:
                print(f"⚠️ 读取 DB{db30_number} 失败: {err}")
            
            # 批量写入检查
            _buffer_count += 1
            if _buffer_count >= _batch_size:
                await _flush_buffer()
                _buffer_count = 0
            
            if poll_count % 12 == 0:
                status = plc.get_status()
                print(f"📊 PLC轮询 #{poll_count} - 连接: {status['connected']}, 错误: {status['error_count']}")
            
            await asyncio.sleep(settings.polling_interval)
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"❌ PLC轮询异常: {e}")
            await asyncio.sleep(5)


# ============================================================
# 数据处理
# ============================================================
def _process_modbus_data(raw_data: bytes):
    """处理 DB32 传感器数据"""
    global _latest_modbus_data, _latest_modbus_timestamp
    
    if not _modbus_parser:
        return

    try:
        # 1. 解析原始数据
        parsed = _modbus_parser.parse_all(raw_data)
        
        # 2. 更新内存缓存 (供实时API使用)
        with _data_lock:
            _latest_modbus_data = parsed
            _latest_modbus_timestamp = datetime.now()
        
        # 3. 转换为 InfluxDB Points (供历史存储)
        # 将 Dict Point 转换为 InfluxDB Point 对象 (因为 write_points_batch 需要 Point 对象)
        now = datetime.now(timezone.utc)
        if _furnace_converter:
            dict_points = _furnace_converter.convert_to_points(parsed, now)
            
            # 存入 buffer
            _point_buffer.extend(dict_points)
            
    except Exception as e:
        print(f"❌ 处理 DB32 数据失败: {e}")


def _process_status_data(raw_data: bytes):
    """处理 DB30 状态数据 (只缓存，不写入数据库)"""
    global _latest_status_data, _latest_status_timestamp
    
    if not _status_parser:
        return

    try:
        parsed = _status_parser.parse_all(raw_data)
        
        with _data_lock:
            _latest_status_data = parsed
            _latest_status_timestamp = datetime.now()
            
    except Exception as e:
        print(f"❌ 处理 DB30 状态数据失败: {e}")


async def _flush_buffer():
    """批量写入缓存数据到 InfluxDB"""
    global _stats
    
    if not _point_buffer:
        return
    
    # 获取 buffer 中的 dict points
    dict_points_list = list(_point_buffer)
    _point_buffer.clear()
    
    # 转换为 InfluxDB Point 对象
    influx_points = []
    for dp in dict_points_list:
        p = build_point(
            dp['measurement'],
            dp['tags'],
            dp['fields'],
            dp['time']
        )
        if p:
            influx_points.append(p)
            
    if not influx_points:
        return

    try:
        # 使用批量写入 (与磨料车间一致: 每10次轮询批量写入)
        success, err = write_points_batch(influx_points)
        if success:
            _stats["successful_writes"] += len(influx_points)
            print(f"✅ 批量写入成功: {len(influx_points)} 个数据点")
        else:
            _stats["failed_writes"] += len(influx_points)
            print(f"❌ 批量写入失败 ({len(influx_points)} 点): {err}")
        
    except Exception as e:
        _stats["failed_writes"] += len(influx_points)
        print(f"❌ 批量写入异常 ({len(influx_points)} 点): {e}")


# ============================================================
# API 数据获取函数
# ============================================================
def get_latest_modbus_data() -> Dict[str, Any]:
    """获取最新的 DB32 传感器数据"""
    with _data_lock:
        return {
            'data': _latest_modbus_data.copy() if _latest_modbus_data else {},
            'timestamp': _latest_modbus_timestamp.isoformat() if _latest_modbus_timestamp else None
        }


def get_latest_status_data() -> Dict[str, Any]:
    """获取最新的 DB30 通信状态数据"""
    with _data_lock:
        return {
            'data': _latest_status_data.copy() if _latest_status_data else {},
            'timestamp': _latest_status_timestamp.isoformat() if _latest_status_timestamp else None
        }


def get_polling_stats() -> Dict[str, Any]:
    """获取轮询统计信息"""
    return {
        'running': _running,
        'stats': _stats.copy(),
        'buffer_size': len(_point_buffer),
        'modbus_data_age': (datetime.now() - _latest_modbus_timestamp).total_seconds() if _latest_modbus_timestamp else None,
        'status_data_age': (datetime.now() - _latest_status_timestamp).total_seconds() if _latest_status_timestamp else None
    }

