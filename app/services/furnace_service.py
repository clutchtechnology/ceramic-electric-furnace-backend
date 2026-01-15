"""
电炉后端 - 电炉数据服务
"""
from typing import List, Dict, Any
from datetime import datetime, timezone

# 电炉配置（后续可从配置文件加载）
FURNACE_CONFIG = [
    {"device_id": "furnace_1", "name": "1号电炉", "zones": 3},
    {"device_id": "furnace_2", "name": "2号电炉", "zones": 3},
    {"device_id": "furnace_3", "name": "3号电炉", "zones": 3},
]

# 实时数据缓存
_realtime_cache: Dict[str, Dict[str, Any]] = {}


def get_furnace_list() -> List[Dict[str, Any]]:
    """获取电炉列表"""
    return FURNACE_CONFIG.copy()


def get_realtime_data() -> List[Dict[str, Any]]:
    """获取所有电炉实时数据"""
    result = []
    
    for furnace in FURNACE_CONFIG:
        device_id = furnace["device_id"]
        cached = _realtime_cache.get(device_id, {})
        
        result.append({
            "device_id": device_id,
            "name": furnace["name"],
            "zones": furnace["zones"],
            "status": cached.get("status", "offline"),
            "temperature": cached.get("temperature", []),
            "power": cached.get("power", 0.0),
            "current": cached.get("current", 0.0),
            "voltage": cached.get("voltage", 0.0),
            "updated_at": cached.get("updated_at", None)
        })
    
    return result


def update_realtime_cache(device_id: str, data: Dict[str, Any]):
    """更新实时数据缓存"""
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    _realtime_cache[device_id] = data


def get_cached_data(device_id: str) -> Dict[str, Any]:
    """获取缓存的实时数据"""
    return _realtime_cache.get(device_id, {})
