"""
前后端桥接层

用于连接 FastAPI 后端逻辑和 PyQt6 前端界面

模块说明：
- data_bridge: Qt 信号桥接器（用于线程间通信，需要 PyQt6）
- data_cache: 内存缓存管理器（用于数据存储，独立模块）
- data_models: 前端数据模型（用于类型提示，独立模块）

使用方式：
- 如果需要 Qt 信号：from frontend.data_bridge import DataBridge
- 如果只需要缓存：from frontend.data_cache import DataCache
- 如果只需要数据模型：from frontend.data_models import ArcData
"""

__version__ = "1.0.0"

# 延迟导入，避免在不需要 PyQt6 时加载
def get_data_bridge():
    """获取数据桥接器（需要 PyQt6）"""
    from .data_bridge import get_data_bridge as _get_data_bridge
    return _get_data_bridge()

# 直接导入不依赖 PyQt6 的模块
from .data_cache import DataCache, get_data_cache
from .data_models import (
    ElectrodeData,
    ArcData,
    CoolingWaterData,
    HopperData,
    ValveStatus,
    DustCollectorData,
    SensorData,
    BatchStatus,
    AlarmRecord,
    HistoryDataPoint,
    dict_to_arc_data,
    dict_to_sensor_data,
    dict_to_batch_status,
)

__all__ = [
    # 桥接器（延迟导入）
    "get_data_bridge",
    # 缓存管理器
    "DataCache",
    "get_data_cache",
    # 数据模型
    "ElectrodeData",
    "ArcData",
    "CoolingWaterData",
    "HopperData",
    "ValveStatus",
    "DustCollectorData",
    "SensorData",
    "BatchStatus",
    "AlarmRecord",
    "HistoryDataPoint",
    # 转换函数
    "dict_to_arc_data",
    "dict_to_sensor_data",
    "dict_to_batch_status",
]

