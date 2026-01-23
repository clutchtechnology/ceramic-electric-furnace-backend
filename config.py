# ============================================================
# 电炉监控后端 - 配置文件
# ============================================================

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置"""
    
    # 服务器配置
    server_host: str = "0.0.0.0"
    server_port: int = 8082  # 电炉后端端口
    debug: bool = False
    
    # ============================================================
    # Mock 模式配置 (核心开关)
    # ============================================================
    # True: 使用 Mock 数据 (开发/测试环境, 无需 PLC 连接)
    # False: 使用真实 PLC 数据 (生产环境)
    # ⚠️ 生产环境默认 False，开发时请在 .env 文件中设置 MOCK_MODE=true
    mock_mode: bool = False  # 🔧 通过环境变量或 .env 文件切换
    
    # PLC 配置 (生产环境固定配置)
    plc_ip: str = "192.168.1.10"  # S7-1200 PLC IP
    plc_port: int = 102
    plc_rack: int = 0
    plc_slot: int = 1
    
    # InfluxDB 配置
    influx_url: str = "http://localhost:8089"
    influx_token: str = "furnace-token"
    influx_org: str = "furnace"
    influx_bucket: str = "sensor_data"
    
    # 轮询配置 (手动启动模式)
    # 🔧 高性能模式: 2秒轮询 (适合电炉高风险场景，几千A电流需要快速响应)
    # 原5秒 → 现2秒 (2.5倍频率提升)
    polling_interval: int = 2  # 秒
    enable_polling: bool = False        # 禁用自动启动，改为手动触发
    
    # DB 块配置
    db32_number: int = 32  # MODBUS_DATA_VALUE (传感器数据)
    db32_size: int = 28    # 读取大小 (不包括 MBrly)
    db30_number: int = 30  # MODBUS_DB_Value (通信状态)
    db30_size: int = 40    # 读取大小
    db33_number: int = 33  # ELECTRICITY_DATA (电表数据)
    db33_size: int = 56    # 读取大小 (14 REAL = 56 bytes)
    
    # 电表配置
    ct_ratio: int = 20     # 电流互感器变比 (100A/5A = 20)
    pt_ratio: int = 1      # 电压互感器变比 (一般为1)
    
    # Modbus RTU 配置 (料仓重量)
    # Windows 宿主机运行: "COM1"
    # Docker 容器运行: "socket://host.docker.internal:7777" (需配合 scripts/process_host_serial_bridge.py)
    modbus_port: str = "COM1"
    modbus_baudrate: int = 19200
    
    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


def reload_settings():
    """重新加载配置 (清除缓存)
    
    用于在运行时切换 mock_mode 后刷新配置
    """
    get_settings.cache_clear()
    return get_settings()
