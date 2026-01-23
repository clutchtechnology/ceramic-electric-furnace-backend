# ============================================================
# 文件说明: valve_config_service.py - 蝶阀配置管理服务
# ============================================================
# 功能:
#   1. 存储和读取4组蝶阀的全开/全关时间配置
#   2. 配置持久化 (使用JSON文件存储)
#   3. 默认全开/全关时间: 30秒
# ============================================================

import json
import os
import threading
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict, field

# 配置文件路径
CONFIG_FILE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "valve_config.json"
)

# 默认配置值
DEFAULT_FULL_ACTION_TIME = 30.0  # 默认全开/全关时间: 30秒


@dataclass
class ValveConfig:
    """单个蝶阀配置"""
    valve_id: int
    full_open_time: float = DEFAULT_FULL_ACTION_TIME   # 全开所需时间(秒)
    full_close_time: float = DEFAULT_FULL_ACTION_TIME  # 全关所需时间(秒)
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ValveConfig':
        return cls(
            valve_id=data.get('valve_id', 1),
            full_open_time=data.get('full_open_time', DEFAULT_FULL_ACTION_TIME),
            full_close_time=data.get('full_close_time', DEFAULT_FULL_ACTION_TIME),
            updated_at=data.get('updated_at', datetime.now().isoformat())
        )


class ValveConfigService:
    """蝶阀配置管理服务 (单例模式)"""
    
    _instance: Optional['ValveConfigService'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._configs: Dict[int, ValveConfig] = {}
        self._config_lock = threading.Lock()
        self._load_configs()
        self._initialized = True
    
    def _load_configs(self):
        """从文件加载配置"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(CONFIG_FILE_PATH), exist_ok=True)
            
            if os.path.exists(CONFIG_FILE_PATH):
                with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for valve_id_str, config_data in data.items():
                        valve_id = int(valve_id_str)
                        self._configs[valve_id] = ValveConfig.from_dict(config_data)
                print(f"✅ 蝶阀配置已加载: {CONFIG_FILE_PATH}")
            else:
                # 创建默认配置
                self._create_default_configs()
                print(f"✅ 创建默认蝶阀配置")
        except Exception as e:
            print(f"⚠️ 加载蝶阀配置失败: {e}, 使用默认配置")
            self._create_default_configs()
    
    def _create_default_configs(self):
        """创建默认配置"""
        for valve_id in range(1, 5):  # 蝶阀1-4
            self._configs[valve_id] = ValveConfig(valve_id=valve_id)
        self._save_configs()
    
    def _save_configs(self):
        """保存配置到文件"""
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE_PATH), exist_ok=True)
            
            data = {
                str(valve_id): config.to_dict()
                for valve_id, config in self._configs.items()
            }
            
            with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 蝶阀配置已保存: {CONFIG_FILE_PATH}")
            return True
        except Exception as e:
            print(f"❌ 保存蝶阀配置失败: {e}")
            return False
    
    def get_config(self, valve_id: int) -> ValveConfig:
        """获取单个蝶阀配置"""
        with self._config_lock:
            if valve_id not in self._configs:
                self._configs[valve_id] = ValveConfig(valve_id=valve_id)
            return self._configs[valve_id]
    
    def get_all_configs(self) -> Dict[int, ValveConfig]:
        """获取所有蝶阀配置"""
        with self._config_lock:
            return self._configs.copy()
    
    def update_config(
        self,
        valve_id: int,
        full_open_time: Optional[float] = None,
        full_close_time: Optional[float] = None
    ) -> ValveConfig:
        """更新单个蝶阀配置"""
        with self._config_lock:
            if valve_id not in self._configs:
                self._configs[valve_id] = ValveConfig(valve_id=valve_id)
            
            config = self._configs[valve_id]
            
            if full_open_time is not None:
                config.full_open_time = max(1.0, full_open_time)  # 最小1秒
            if full_close_time is not None:
                config.full_close_time = max(1.0, full_close_time)  # 最小1秒
            
            config.updated_at = datetime.now().isoformat()
            self._save_configs()
            
            print(f"📝 蝶阀{valve_id}配置已更新: 全开={config.full_open_time}s, 全关={config.full_close_time}s")
            return config
    
    def update_all_configs(
        self,
        configs: Dict[int, Dict[str, float]]
    ) -> Dict[int, ValveConfig]:
        """批量更新蝶阀配置
        
        Args:
            configs: {
                1: {"full_open_time": 30.0, "full_close_time": 30.0},
                2: {"full_open_time": 35.0, "full_close_time": 35.0},
                ...
            }
        """
        with self._config_lock:
            for valve_id, config_data in configs.items():
                if valve_id not in self._configs:
                    self._configs[valve_id] = ValveConfig(valve_id=valve_id)
                
                config = self._configs[valve_id]
                
                if 'full_open_time' in config_data:
                    config.full_open_time = max(1.0, config_data['full_open_time'])
                if 'full_close_time' in config_data:
                    config.full_close_time = max(1.0, config_data['full_close_time'])
                
                config.updated_at = datetime.now().isoformat()
            
            self._save_configs()
            print(f"📝 批量更新蝶阀配置完成: {len(configs)}个")
            return self._configs.copy()
    
    def reset_to_default(self, valve_id: Optional[int] = None):
        """重置为默认配置"""
        with self._config_lock:
            if valve_id is not None:
                self._configs[valve_id] = ValveConfig(valve_id=valve_id)
            else:
                self._create_default_configs()
            self._save_configs()


# ============================================================
# 便捷函数
# ============================================================
def get_valve_config_service() -> ValveConfigService:
    """获取蝶阀配置服务实例"""
    return ValveConfigService()


def get_valve_full_action_times() -> Dict[int, Dict[str, float]]:
    """获取所有蝶阀的全开/全关时间
    
    Returns:
        {
            1: {"full_open_time": 30.0, "full_close_time": 30.0},
            2: {"full_open_time": 30.0, "full_close_time": 30.0},
            ...
        }
    """
    service = get_valve_config_service()
    configs = service.get_all_configs()
    return {
        valve_id: {
            "full_open_time": config.full_open_time,
            "full_close_time": config.full_close_time
        }
        for valve_id, config in configs.items()
    }
