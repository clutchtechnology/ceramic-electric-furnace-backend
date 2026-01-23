# ============================================================
# 文件说明: polling_service.py - 数据轮询核心服务
# ============================================================
# 功能:
#   1. 轮询服务状态管理 (启动/停止)
#   2. 批次号管理 - 代理到 BatchService (唯一状态源)
#   3. 统一API接口 (供路由层调用)
# ============================================================
# 架构说明:
#   - polling_data_generator.py: Mock数据生成
#   - polling_data_processor.py: 数据处理和缓存管理
#   - polling_service.py: 核心服务和状态管理 (本文件)
#   - batch_service.py: 批次状态管理 (唯一状态源)
# ============================================================

from datetime import datetime
from typing import Optional, Dict, Any

from config import get_settings

# 导入数据处理模块
from app.services.polling_data_processor import (
    init_parsers,
    get_latest_modbus_data,
    get_latest_arc_data,
    get_latest_status_data,
    get_latest_db41_data,
    get_latest_weight_data,
    get_valve_status_queues,
    get_buffer_status,
)

# 导入批次服务 (唯一状态源)
from app.services.batch_service import get_batch_service

settings = get_settings()

# ============================================================
# Modbus RTU 配置
# ============================================================
MODBUS_PORT = "COM1"
MODBUS_BAUDRATE = 19200


# ============================================================
# 轮询服务状态管理
# ============================================================
def get_polling_status():
    """获取轮询服务状态"""
    from app.services.polling_loops_v2 import get_polling_loops_status
    loops_status = get_polling_loops_status()
    buffer_status = get_buffer_status()
    
    # 从 BatchService 获取批次信息 (唯一状态源)
    batch_service = get_batch_service()
    batch_status = batch_service.get_status()
    
    return {
        "is_running": loops_status['db1_running'],
        "batch_code": batch_status['batch_code'],
        "start_time": batch_status['start_time'],
        "is_smelting": batch_status['is_smelting'],
        "mode": "mock" if settings.mock_mode else "plc",
        "statistics": buffer_status['stats']
    }


# ============================================================
# 批次号管理函数 (代理到 BatchService)
# ============================================================
def _generate_batch_code(furnace_number: int = 3) -> str:
    """生成批次号
    
    格式: FFYYMMDD (8位数字，无分隔符)
    - FF: 炉号 (01-99)
    - YY: 年份后两位 (26 = 2026)
    - MM: 月份 (01-12)
    - DD: 日期 (01-31)
    
    示例: 03260123 = 3号炉 + 2026年1月23日
    """
    now = datetime.now()
    furnace = str(furnace_number).zfill(2)
    year = str(now.year % 100).zfill(2)  # 只取后两位
    month = str(now.month).zfill(2)
    day = str(now.day).zfill(2)
    return f"{furnace}{year}{month}{day}"


def ensure_batch_code() -> Optional[str]:
    """获取当前批次号
    
    重要: 批次号仅由前端通过 start_smelting API 提供
    后端不再自动生成批次号，避免产生混乱的数据
    
    Returns:
        str: 当前批次号，如果没有则返回 None
    """
    batch_service = get_batch_service()
    return batch_service.batch_code


def start_smelting(batch_code: Optional[str] = None) -> Dict[str, Any]:
    """开始冶炼 (前端调用)
    
    代理到 BatchService.start()，确保状态统一
    新批次开始时会重置蝶阀开度为0%
    
    重要: 批次号必须由前端提供，后端不再自动生成
    """
    batch_service = get_batch_service()
    
    # [重要] 批次号必须由前端提供
    if not batch_code:
        print("⚠️ 开始冶炼失败: 未提供批次号")
        return {
            'batch_code': None,
            'start_time': None,
            'is_smelting': False,
            'error': '批次号必须由前端提供，请在开始冶炼时传入 batch_code'
        }
    
    # 调用 BatchService 开始冶炼 (唯一状态源)
    result = batch_service.start(batch_code)
    
    if not result['success']:
        print(f"⚠️ 开始冶炼失败: {result['message']}")
        return {
            'batch_code': result.get('batch_code'),
            'start_time': None,
            'is_smelting': batch_service.is_smelting,
            'error': result['message']
        }
    
    # ========================================
    # 重置蝶阀开度 (新批次从0%开始)
    # ========================================
    try:
        from app.services.valve_calculator_service import reset_all_valve_openness
        reset_all_valve_openness(batch_code=batch_code)
        print(f"🔄 蝶阀开度已重置 (批次: {batch_code})")
    except Exception as e:
        print(f"⚠️ 重置蝶阀开度失败: {e}")
        
    print(f"🔥 开始冶炼, 批次号: {batch_code}")
    
    return {
        'batch_code': result['batch_code'],
        'start_time': result.get('start_time'),
        'is_smelting': True
    }


def stop_smelting() -> Dict[str, Any]:
    """停止冶炼 (前端调用)
    
    代理到 BatchService.stop()，确保状态统一
    """
    batch_service = get_batch_service()
    
    # 记录旧批次信息
    old_batch_code = batch_service.batch_code
    old_start_time = batch_service.start_time
    
    # 调用 BatchService 停止冶炼 (唯一状态源)
    result = batch_service.stop()
    
    if not result['success']:
        print(f"⚠️ 停止冶炼失败: {result['message']}")
        return {
            'batch_code': old_batch_code,
            'start_time': old_start_time.isoformat() if old_start_time else None,
            'end_time': datetime.now().isoformat(),
            'is_smelting': batch_service.is_smelting,
            'error': result['message']
        }
        
    print(f"⏹️ 停止冶炼, 批次号: {old_batch_code}")
    
    summary = result.get('summary', {})
    return {
        'batch_code': summary.get('batch_code', old_batch_code),
        'start_time': summary.get('start_time'),
        'end_time': summary.get('end_time', datetime.now().isoformat()),
        'is_smelting': False
    }


def get_batch_info() -> Dict[str, Any]:
    """获取当前批次信息
    
    代理到 BatchService.get_status()，确保状态统一
    """
    batch_service = get_batch_service()
    status = batch_service.get_status()
    
    return {
        'batch_code': status['batch_code'],
        'start_time': status['start_time'],
        'is_smelting': status['is_smelting'],
        'is_running': status['is_running'],
        'duration_seconds': status['elapsed_seconds']
    }


# ============================================================
# 统一API接口 (供路由层调用)
# ============================================================
def get_polling_stats() -> Dict[str, Any]:
    """获取轮询统计信息"""
    buffer_status = get_buffer_status()
    batch_service = get_batch_service()
    
    return {
        'batch_code': batch_service.batch_code,
        'is_smelting': batch_service.is_smelting,
        'buffer_status': buffer_status
    }


# ============================================================
# 模块初始化
# ============================================================
def initialize_service():
    """初始化轮询服务"""
    print("🚀 初始化轮询服务...")
    init_parsers()
    print("✅ 轮询服务初始化完成")
