"""
#3电炉 - PyQt6 GUI 入口

单进程多线程架构：
- 主线程: PyQt6 GUI
- 工作线程1: PLC 弧流轮询（0.2s）
- 工作线程2: PLC 传感器轮询（2s）
- 工作线程3: InfluxDB 写入
"""
import sys
import os
from pathlib import Path

# 添加项目路径到 sys.path
BASE_DIR = Path(__file__).resolve().parent
PYQT_DIR = BASE_DIR.parent / "ceramic-electric-furnace-pyqt"

# 确保可以导入前端模块
if str(PYQT_DIR) not in sys.path:
    sys.path.insert(0, str(PYQT_DIR))

# 确保可以导入后端模块
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
import logging

# 1. 配置根日志记录器（只显示 WARNING 及以上级别的第三方库日志）
logging.basicConfig(
    level=logging.WARNING,  # 第三方库只显示警告和错误
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(BASE_DIR / 'logs' / 'gui.log', encoding='utf-8')
    ]
)

# 2. 为我们自己的模块设置 INFO 级别
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 3. 为项目相关的模块设置 INFO 级别
for module_name in ['app', 'frontend', 'ui', 'config']:
    logging.getLogger(module_name).setLevel(logging.INFO)

# 4. 禁用一些特别吵闹的第三方库日志
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.WARNING)
logging.getLogger('PyQt6').setLevel(logging.WARNING)
logging.getLogger('matplotlib').setLevel(logging.WARNING)


def main():
    """应用入口"""
    logger.info("=" * 60)
    logger.info("🚀 #3电炉启动 (PyQt6 单进程版本)")
    logger.info("=" * 60)
    
    # 显示配置信息
    from config import get_settings
    settings = get_settings()
    
    if settings.mock_mode:
        logger.info("🧪 当前模式: Mock (开发/测试环境)")
        logger.info("   - 使用随机生成的模拟数据")
        logger.info("   - 无需 PLC 连接")
    else:
        logger.info("🏭 当前模式: PLC (生产环境)")
        logger.info(f"   - PLC IP: {settings.plc_ip}:{settings.plc_port}")
        logger.info(f"   - Modbus: {settings.modbus_port} @ {settings.modbus_baudrate}")
    
    logger.info("-" * 60)
    
    # 创建 Qt 应用
    app = QApplication(sys.argv)
    app.setApplicationName("#3电炉")
    app.setOrganizationName("Clutch Team")
    
    # 设置高 DPI 支持
    app.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    
    try:
        # 导入主窗口（延迟导入，确保 QApplication 已创建）
        from ui.main_window import MainWindow
        
        # 创建主窗口
        window = MainWindow()
        
        # 全屏显示
        window.showFullScreen()
        
        logger.info("✅ 主窗口已启动")
        logger.info("=" * 60)
        
        # 运行应用
        sys.exit(app.exec())
    
    except ImportError as e:
        logger.error(f"❌ 导入错误: {e}")
        logger.error("提示: 请确保已创建 ui/main_window.py 文件")
        sys.exit(1)
    
    except Exception as e:
        logger.error(f"❌ 启动失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

