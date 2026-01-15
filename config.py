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
    
    # PLC 配置
    plc_ip: str = "192.168.1.10"
    plc_port: int = 102
    plc_rack: int = 0
    plc_slot: int = 1
    
    # InfluxDB 配置
    influx_url: str = "http://localhost:8088"
    influx_token: str = "furnace-token"
    influx_org: str = "furnace"
    influx_bucket: str = "sensor_data"
    
    # 轮询配置
    polling_interval: int = 5  # 秒
    enable_polling: bool = False      # 真实 PLC 轮询
    enable_mock_polling: bool = True  # Mock 数据轮询 (开发测试)
    
    # Mock 数据配置
    use_mock_data: bool = True
    
    # DB 块配置
    db32_number: int = 32  # MODBUS_DATA_VALUE (传感器数据)
    db32_size: int = 28    # 读取大小 (不包括 MBrly)
    db30_number: int = 30  # MODBUS_DB_Value (通信状态)
    db30_size: int = 40    # 读取大小
    
    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
