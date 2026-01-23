#!/usr/bin/env python3
# ============================================================
# 文件说明: mock_plc_server.py - 模拟S7-1200 PLC服务器
# ============================================================
# 功能:
# 1. 模拟真实的S7-1200 PLC，可被正式轮询代码连接
# 2. 提供DB30/DB32/DB33读取服务
# 3. 使用 snap7 库作为服务器
# 4. 配合 mock_data_generator 生成动态数据
#
# 使用场景:
#   测试真实轮询代码（不使用Mock模式）
#   验证PLC连接逻辑
#
# 使用方法:
#   1. 启动此服务: python tests/mock/mock_plc_server.py
#   2. 修改 config.py: plc_ip = "127.0.0.1"
#   3. 启动正式后端: python main.py
#
# 停止方法:
#   Ctrl+C
# ============================================================

import sys
import os
import time
import signal
import threading
from typing import Dict

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

try:
    import snap7
    from snap7.server import Server
    SNAP7_AVAILABLE = True
except ImportError:
    SNAP7_AVAILABLE = False
    print("❌ snap7 未安装，无法启动Mock PLC服务器")
    print("   安装方法: pip install python-snap7")
    sys.exit(1)

from tests.mock.mock_data_generator import MockDataGenerator

# ============================================================
# 配置
# ============================================================
PLC_IP = "0.0.0.0"  # 监听所有网络接口
PLC_PORT = 102      # S7 默认端口

UPDATE_INTERVAL = 5  # 数据更新间隔 (秒)

# DB块大小定义
DB_SIZES = {
    30: 40,  # DB30: 通信状态 (40 bytes)
    32: 28,  # DB32: 传感器数据 (28 bytes, 不含写寄存器)
    33: 56,  # DB33: 电表数据 (56 bytes)
}

# ============================================================
# 全局变量
# ============================================================
_server: Optional[Server] = None
_generator: Optional[MockDataGenerator] = None
_is_running = True
_update_thread: Optional[threading.Thread] = None


def signal_handler(sig, frame):
    """处理Ctrl+C信号"""
    global _is_running
    print("\n⏹️  收到停止信号，正在退出...")
    _is_running = False


def update_db_data():
    """定期更新DB块数据"""
    global _is_running, _server, _generator
    
    print("🔄 数据更新线程启动")
    
    while _is_running:
        try:
            # 生成新数据
            all_db_data = _generator.generate_all_db_data()
            
            # 写入各DB块
            for db_number, raw_data in all_db_data.items():
                if _server:
                    _server.set_area(
                        snap7.types.S7AreaDB,
                        db_number,
                        0,  # start offset
                        bytearray(raw_data)
                    )
            
            # 打印更新统计
            timestamp = time.strftime("%H:%M:%S")
            print(f"[{timestamp}] 数据已更新 - DB30/DB32/DB33")
            
        except Exception as e:
            print(f"❌ 数据更新错误: {e}")
        
        # 等待下次更新
        time.sleep(UPDATE_INTERVAL)
    
    print("🔄 数据更新线程已停止")


def start_mock_plc_server():
    """启动模拟PLC服务器"""
    global _server, _generator, _is_running, _update_thread
    
    print("=" * 60)
    print("🚀 电炉 Mock PLC 服务器启动")
    print("=" * 60)
    print(f"📡 监听地址: {PLC_IP}:{PLC_PORT}")
    print(f"📦 提供服务: DB30 (40B), DB32 (28B), DB33 (56B)")
    print(f"🔄 数据更新: 每 {UPDATE_INTERVAL} 秒")
    print("=" * 60)
    print("按 Ctrl+C 停止服务")
    print("=" * 60)
    
    # 初始化数据生成器
    _generator = MockDataGenerator()
    
    # 创建 Snap7 服务器
    _server = Server()
    
    # 注册DB块
    for db_number, db_size in DB_SIZES.items():
        _server.register_area(
            snap7.types.S7AreaDB,
            db_number,
            bytearray(db_size)
        )
        print(f"✅ DB{db_number} 已注册 ({db_size} bytes)")
    
    # 初始化数据
    print("\n📊 生成初始数据...")
    all_db_data = _generator.generate_all_db_data()
    for db_number, raw_data in all_db_data.items():
        _server.set_area(
            snap7.types.S7AreaDB,
            db_number,
            0,
            bytearray(raw_data)
        )
    print("✅ 初始数据已写入")
    
    # 启动数据更新线程
    _update_thread = threading.Thread(target=update_db_data, daemon=True)
    _update_thread.start()
    
    # 启动服务器
    print(f"\n🎯 服务器监听中: {PLC_IP}:{PLC_PORT}")
    _server.start(tcpport=PLC_PORT)
    
    try:
        # 保持运行
        while _is_running:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        # 停止服务器
        print("\n⏹️  正在停止服务器...")
        _server.stop()
        print("✅ Mock PLC 服务器已停止")


def main():
    """主入口"""
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 启动服务器
    start_mock_plc_server()


if __name__ == "__main__":
    main()
