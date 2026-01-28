# ============================================================
# 文件说明: polling_loops_v2.py - 独立的三速轮询架构
# ============================================================
# 功能:
#   1. DB1 弧流弧压轮询 (可变速: 5s/0.2s)
#   2. DB32 传感器轮询 (固定: 5s)
#   3. DB30/DB41 状态轮询 (固定: 5s, 仅缓存)
# ============================================================
# 设计原则:
#   - 三个独立的 asyncio.Task
#   - 自动启动 (无需前端触发)
#   - 开始冶炼时切换 DB1 速度
# ============================================================
# 【数据库写入说明 - 轮询架构】
# ============================================================
# 1: DB1 弧流弧压轮询 (_db1_arc_polling_loop)
#    - 轮询间隔: 5秒(默认) / 0.2秒(冶炼中)
#    - 批量写入: 20次轮询后写入 (4秒)
#    - 写入条件: 必须有批次号(batch_code)且冶炼状态为running/paused
#    - 数据点: 弧流(3) + 弧压(3) + 设定值(3,仅变化) + 死区(1,仅变化)
# ============================================================
# 2: DB32 传感器轮询 (_db32_sensor_polling_loop)
#    - 轮询间隔: 0.5秒
#    - 批量写入: 30次轮询后写入 (15秒)
#    - 写入条件: 必须有批次号(batch_code)且冶炼状态为running/paused
#    - 数据点: 电极深度(3) + 冷却水压力(2) + 冷却水流量(2) + 冷却水累计(2)
# ============================================================
# 3: 料仓重量轮询 (与DB32同步)
#    - 轮询间隔: 0.5秒
#    - 批量写入: 30次轮询后写入 (15秒)
#    - 写入条件: 必须有批次号(batch_code)且冶炼状态为running/paused
#    - 数据点: 净重(1) + 投料累计(1) + 投料状态(1)
# ============================================================
# 4: DB30/DB41 状态轮询 (_status_polling_loop)
#    - 轮询间隔: 5秒
#    - 写入: 不写入数据库，仅内存缓存
#    - 数据点: 通信状态 + 数据有效性状态
# ============================================================

import asyncio
import traceback
from datetime import datetime, timezone
from typing import Optional

from config import get_settings
from app.plc.plc_manager import get_plc_manager

settings = get_settings()

# ============================================================
# 全局变量 (轮询任务)
# ============================================================
_db1_task: Optional[asyncio.Task] = None
_db32_task: Optional[asyncio.Task] = None
_status_task: Optional[asyncio.Task] = None

# 运行标志
_db1_running = False
_db32_running = False
_status_running = False

# DB1 轮询间隔 (秒) - 可动态修改
_db1_interval: float = 5.0  # 默认5s, 开始冶炼后改为0.2s

# 批量写入缓存 (与旧架构保持一致)
_arc_buffer_count = 0
_arc_batch_size = 20  # 🔥 DB1: 20次轮询后写入 (0.2s×20=4s)

_normal_buffer_count = 0
_normal_batch_size = 30  # 📊 DB32: 30次轮询后写入 (0.5s×30=15s)

_valve_buffer_count = 0
_valve_batch_size = 30  # 🔧 Valve: 30次轮询后写入 (0.5s×30=15s)


# ============================================================
# 1: 批量写入函数模块
# ============================================================
async def _flush_arc_buffer():
    """批量写入 DB1 弧流弧压缓存"""
    from app.services.polling_data_processor import flush_arc_buffer
    await flush_arc_buffer()


async def _flush_normal_buffer():
    """批量写入 DB32/重量缓存"""
    from app.services.polling_data_processor import flush_normal_buffer
    await flush_normal_buffer()


async def _flush_valve_buffer():
    """批量写入蝶阀开度缓存"""
    from app.services.valve_calculator_service import flush_valve_openness_buffers
    await flush_valve_openness_buffers()


# ============================================================
# 2: 状态查询函数模块
# ============================================================
def get_polling_loops_status() -> dict:
    """获取所有轮询循环的状态
    
    Returns:
        dict: {
            'db1_running': bool,
            'db32_running': bool,
            'status_running': bool,
            'db1_interval': float
        }
    """
    return {
        'db1_running': _db1_running,
        'db32_running': _db32_running,
        'status_running': _status_running,
        'db1_interval': _db1_interval
    }


# ============================================================
# 3: DB1 弧流弧压轮询模块 (可变速)
# ============================================================
async def _db1_arc_polling_loop(
    parser,
    process_func,
    is_mock: bool = False
):
    """DB1 弧流弧压轮询 (可变速: 5s -> 0.2s)
    
    Args:
        parser: DB1 解析器
        process_func: 数据处理函数
        is_mock: 是否 Mock 模式
    """
    global _db1_interval, _arc_buffer_count, _arc_batch_size
    poll_count = 0
    error_count = 0  # 连续错误计数器
    MAX_ERROR_WAIT = 30  # 最大等待时间 (秒)
    
    print(f"🔥 DB1 弧流弧压轮询已启动 (初始间隔: {_db1_interval}s)")
    
    if not is_mock:
        plc = get_plc_manager()
        db_number = parser.get_db_number() if parser else 1
        db_size = parser.get_total_size() if parser else 182
    
    while _db1_running:
        try:
            poll_count += 1
            
            if is_mock:
                # Mock 模式: 生成随机数据
                from app.services.polling_data_generator import generate_mock_db1_data
                db1_data = generate_mock_db1_data()
            else:
                # PLC 模式: 读取真实数据
                if not plc.is_connected():
                    plc.connect()
                
                result = plc.read_db(db_number, 0, db_size)
                if isinstance(result, (tuple, list)) and len(result) == 2:
                    db1_data, err = result
                else:
                    db1_data = None
                
                if not db1_data:
                    await asyncio.sleep(1)
                    continue
            
            # 处理数据 (获取当前批次号)
            from app.services.polling_service import get_batch_info
            batch_info = get_batch_info()
            current_batch = batch_info.get('batch_code')
            is_smelting = batch_info.get('is_smelting', False)
            
            # 只有在冶炼状态（running 或 paused）时才处理数据
            # 断电恢复后状态为 running，batch_code 存在，会继续处理数据
            if is_smelting and current_batch:
                process_func(db1_data, current_batch)
            
            # 批量写入逻辑
            _arc_buffer_count += 1
            if _arc_buffer_count >= _arc_batch_size:
                await _flush_arc_buffer()
                _arc_buffer_count = 0
            
            # 成功后重置错误计数器
            error_count = 0
            
            # 日志输出
            if poll_count % 25 == 0:
                print(f"🔥 DB1 轮询 #{poll_count} (间隔: {_db1_interval}s, 缓存: {_arc_buffer_count}/{_arc_batch_size})")
            
            # 动态间隔 (可被外部修改)
            await asyncio.sleep(_db1_interval)
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            error_count += 1
            # 指数退避: 1s, 2s, 4s, 8s, 16s, 30s (最大)
            wait_time = min(MAX_ERROR_WAIT, 2 ** min(error_count - 1, 4))
            print(f"❌ DB1 轮询异常 (第{error_count}次): {e}")
            if error_count <= 3:
                traceback.print_exc()
            elif error_count % 10 == 0:
                # 每10次错误输出一次详细堆栈，避免日志爆炸
                print(f"⚠️ DB1 连续 {error_count} 次错误，等待 {wait_time}s 后重试...")
                traceback.print_exc()
            await asyncio.sleep(wait_time)
    
    print("🔥 DB1 弧流弧压轮询已停止")


# ============================================================
# 4: DB32 传感器轮询模块 (固定 0.5s)
# ============================================================
async def _db32_sensor_polling_loop(
    parser,
    process_func,
    weight_reader_func,
    is_mock: bool = False
):
    """DB32 传感器 + 料仓重量轮询 (固定 0.5s)
    
    Args:
        parser: DB32 解析器
        process_func: 数据处理函数
        weight_reader_func: 料仓重量读取函数
        is_mock: 是否 Mock 模式
    """
    global _normal_buffer_count, _normal_batch_size
    poll_count = 0
    error_count = 0  # 连续错误计数器
    MAX_ERROR_WAIT = 30  # 最大等待时间 (秒)
    interval = 0.5  # 固定 0.5s (1秒2次轮询)
    weight_poll_interval = 1  # 每次DB32轮询都读重量 (0.5s)
    
    print(f"📊 DB32 传感器轮询已启动 (间隔: {interval}s)")
    
    if not is_mock:
        plc = get_plc_manager()
        db_number = parser.get_db_number() if parser else 32
        db_size = parser.get_total_size() if parser else 29
    
    while _db32_running:
        try:
            poll_count += 1
            
            # 1. 读取 DB32 传感器数据
            if is_mock:
                from app.services.polling_data_generator import generate_mock_db32_data
                db32_data = generate_mock_db32_data()
            else:
                if not plc.is_connected():
                    plc.connect()
                
                result = plc.read_db(db_number, 0, db_size)
                if isinstance(result, (tuple, list)) and len(result) == 2:
                    db32_data, err = result
                else:
                    db32_data = None
                
                if not db32_data:
                    await asyncio.sleep(1)
                    continue
            
            process_func(db32_data)
            
            # 2. 读取料仓重量 (Modbus RTU) + PLC 投料信号 (%Q3.7, %Q4.0)
            if poll_count % weight_poll_interval == 0:
                # 2.1 读取投料信号 (Q 区)
                is_discharging = False
                is_requesting = False
                
                if not is_mock:
                    try:
                        # 读取 Q3 和 Q4 (2字节)
                        q_data, q_err = plc.read_output_area(3, 2)
                        if q_data:
                            # %Q3.7 = Q3 的第7位
                            is_discharging = bool((q_data[0] >> 7) & 0x01)
                            # %Q4.0 = Q4 的第0位
                            is_requesting = bool(q_data[1] & 0x01)
                    except Exception as q_err:
                        pass  # 读取失败时使用默认值 False
                
                # 2.2 读取料仓重量
                if is_mock:
                    from app.services.polling_data_generator import generate_mock_weight_data
                    weight_data = generate_mock_weight_data()
                else:
                    weight_data = weight_reader_func(
                        port=settings.modbus_port,
                        baudrate=settings.modbus_baudrate
                    )
                
                # 2.3 处理重量数据 (传入投料信号)
                from app.services.polling_service import get_batch_info
                from app.services.polling_data_processor import process_weight_data
                batch_info = get_batch_info()
                current_batch = batch_info.get('batch_code')
                is_smelting = batch_info.get('is_smelting', False)
                
                # 只有在冶炼状态（running 或 paused）时才处理数据
                # 断电恢复后状态为 running，batch_code 存在，会继续处理数据
                if is_smelting and current_batch:
                    process_weight_data(
                        weight_data,
                        current_batch,
                        is_discharging=is_discharging,
                        is_requesting=is_requesting
                    )
            
            # 批量写入逻辑 (每15秒写一次: 0.5s×30=15s)
            _normal_buffer_count += 1
            if _normal_buffer_count >= _normal_batch_size:
                await _flush_normal_buffer()
                _normal_buffer_count = 0
            
            # 蝶阀开度批量写入逻辑 (每15秒写一次: 0.5s×30=15s)
            _valve_buffer_count += 1
            if _valve_buffer_count >= _valve_batch_size:
                await _flush_valve_buffer()
                _valve_buffer_count = 0
            
            # 成功后重置错误计数器
            error_count = 0
            
            # 日志输出 (每60次=30秒输出一次)
            if poll_count % 60 == 0:
                print(f"📊 DB32 轮询 #{poll_count} (缓存: {_normal_buffer_count}/{_normal_batch_size}, 蝶阀: {_valve_buffer_count}/{_valve_batch_size})")
            
            await asyncio.sleep(interval)
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            error_count += 1
            # 指数退避: 1s, 2s, 4s, 8s, 16s, 30s (最大)
            wait_time = min(MAX_ERROR_WAIT, 2 ** min(error_count - 1, 4))
            print(f"❌ DB32 轮询异常 (第{error_count}次): {e}")
            if error_count <= 3:
                traceback.print_exc()
            elif error_count % 10 == 0:
                print(f"⚠️ DB32 连续 {error_count} 次错误，等待 {wait_time}s 后重试...")
            await asyncio.sleep(wait_time)
    
    print("📊 DB32 传感器轮询已停止")


# ============================================================
# 5: DB30/DB41 状态轮询模块 (固定 5s, 仅缓存)
# ============================================================
async def _status_polling_loop(
    db30_parser,
    db41_parser,
    process_db30_func,
    process_db41_func,
    is_mock: bool = False
):
    """DB30/DB41 状态轮询 (固定 5s, 仅缓存)
    
    Args:
        db30_parser: DB30 解析器
        db41_parser: DB41 解析器
        process_db30_func: DB30 处理函数
        process_db41_func: DB41 处理函数
        is_mock: 是否 Mock 模式
    """
    poll_count = 0
    error_count = 0  # 连续错误计数器
    MAX_ERROR_WAIT = 30  # 最大等待时间 (秒)
    interval = 5.0  # 固定 5s
    
    print(f"📡 状态轮询已启动 (DB30+DB41, 间隔: {interval}s)")
    
    if not is_mock:
        plc = get_plc_manager()
        db30_number = db30_parser.get_db_number() if db30_parser else 30
        db30_size = db30_parser.get_total_size() if db30_parser else 40
        db41_number = db41_parser.get_db_number() if db41_parser else 41
        db41_size = db41_parser.get_total_size() if db41_parser else 28  # 7设备×4字节=28
    
    while _status_running:
        try:
            poll_count += 1
            
            # 1. 读取 DB30 通信状态
            if is_mock:
                from app.services.polling_data_generator import generate_mock_db30_data
                db30_data = generate_mock_db30_data()
            else:
                if not plc.is_connected():
                    plc.connect()
                
                result = plc.read_db(db30_number, 0, db30_size)
                if isinstance(result, (tuple, list)) and len(result) == 2:
                    db30_data, err = result
                else:
                    db30_data = None
            
            if db30_data:
                process_db30_func(db30_data)
            
            # 2. 读取 DB41 数据状态
            if is_mock:
                from app.services.polling_data_generator import generate_mock_db41_data
                db41_data = generate_mock_db41_data()
            else:
                result = plc.read_db(db41_number, 0, db41_size)
                if isinstance(result, (tuple, list)) and len(result) == 2:
                    db41_data, err = result
                else:
                    db41_data = None
            
            if db41_data:
                process_db41_func(db41_data)
            
            # 成功后重置错误计数器
            error_count = 0
            
            # 日志输出
            if poll_count % 12 == 0:
                print(f"📡 状态轮询 #{poll_count}")
            
            await asyncio.sleep(interval)
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            error_count += 1
            # 指数退避: 1s, 2s, 4s, 8s, 16s, 30s (最大)
            wait_time = min(MAX_ERROR_WAIT, 2 ** min(error_count - 1, 4))
            print(f"❌ 状态轮询异常 (第{error_count}次): {e}")
            if error_count <= 3:
                traceback.print_exc()
            elif error_count % 10 == 0:
                print(f"⚠️ 状态轮询连续 {error_count} 次错误，等待 {wait_time}s 后重试...")
            await asyncio.sleep(wait_time)
    
    print("📡 状态轮询已停止")


# ============================================================
# 启动/停止函数 (供 main.py 调用)
# ============================================================
async def start_all_polling_loops():
    """启动所有轮询任务 (自动启动)"""
    global _db1_task, _db32_task, _status_task
    global _db1_running, _db32_running, _status_running
    global _db1_interval
    
    from app.services.polling_data_processor import (
        init_parsers,
        get_parsers,
        process_arc_data,
        process_modbus_data,
        process_status_data,
        process_db41_data,
    )
    from app.tools.operation_modbus_weight_reader import read_hopper_weight
    
    # 初始化解析器
    init_parsers()
    
    # 获取解析器
    db1_parser, modbus_parser, status_parser, db41_parser = get_parsers()
    
    # 重置间隔为默认值 (5s)
    _db1_interval = 5.0
    
    # 启动标志
    _db1_running = True
    _db32_running = True
    _status_running = True
    
    is_mock = settings.mock_mode
    mode_text = "Mock" if is_mock else "PLC"
    
    print("=" * 60)
    print(f"🚀 启动三速轮询架构 ({mode_text} 模式)")
    print("   🔥 DB1 弧流弧压: 5s (可切换到 0.2s)")
    print("   📊 DB32 传感器: 0.5s (高频, 含冷却水流量计算)")
    print("   📡 DB30/DB41 状态: 5s (固定)")
    print("=" * 60)
    
    # 创建任务
    _db1_task = asyncio.create_task(_db1_arc_polling_loop(
        db1_parser,
        process_arc_data,
        is_mock=is_mock
    ))
    
    _db32_task = asyncio.create_task(_db32_sensor_polling_loop(
        modbus_parser,
        process_modbus_data,
        read_hopper_weight,
        is_mock=is_mock
    ))
    
    _status_task = asyncio.create_task(_status_polling_loop(
        status_parser,
        db41_parser,
        process_status_data,
        process_db41_data,
        is_mock=is_mock
    ))


async def stop_all_polling_loops():
    """停止所有轮询任务"""
    global _db1_task, _db32_task, _status_task
    global _db1_running, _db32_running, _status_running
    
    _db1_running = False
    _db32_running = False
    _status_running = False
    
    tasks = [_db1_task, _db32_task, _status_task]
    for task in tasks:
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    
    print("🛑 所有轮询任务已停止")


def switch_db1_speed(high_speed: bool):
    """切换 DB1 轮询速度
    
    Args:
        high_speed: True=0.2s (冶炼中), False=5s (空闲)
    """
    global _db1_interval
    
    if high_speed:
        _db1_interval = 0.2
        print("🔥 DB1 轮询切换到高速模式 (0.2s)")
    else:
        _db1_interval = 5.0
        print("🔥 DB1 轮询切换到低速模式 (5.0s)")


def get_polling_loops_status():
    """获取轮询任务状态"""
    return {
        "db1_running": _db1_running,
        "db1_interval": _db1_interval,
        "db32_running": _db32_running,
        "status_running": _status_running,
    }
