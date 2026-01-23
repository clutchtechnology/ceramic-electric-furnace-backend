import sys
import os

# 尝试导入 pyserial 的 tcp_serial_redirect 工具
try:
    from serial.tools import tcp_serial_redirect
except ImportError:
    print("❌ 错误: 未安装 pyserial 库。")
    print("请先运行: pip install pyserial")
    sys.exit(1)

# ============================================================
# 配置 - 修改此处以适配环境
# ============================================================
SERIAL_PORT = 'COM1'    # 宿主机物理串口
BAUDRATE = 19200        # 波特率
TCP_PORT = 7777         # 暴露给 Docker 的端口

def main():
    print(f"========================================================")
    print(f"   🔥 串口转发网桥 (Host -> Docker)")
    print(f"========================================================")
    print(f"   物理串口: {SERIAL_PORT} @ {BAUDRATE}")
    print(f"   转发地址: 0.0.0.0:{TCP_PORT}")
    print(f"   Docker内配置: socket://host.docker.internal:{TCP_PORT}")
    print(f"--------------------------------------------------------")
    print(f"   提示: 请保持此窗口开启，不要关闭！")
    print(f"========================================================\n")

    # 构造参数模拟命令行调用
    # 相当于运行: python -m serial.tools.tcp_serial_redirect -P 7777 COM1 19200
    sys.argv = [
        'tcp_serial_redirect.py',
        '-P', str(TCP_PORT),
        '--rts', '0',  # 某些设备可能需要控制流控
        '--dtr', '0',
        SERIAL_PORT,
        str(BAUDRATE)
    ]

    try:
        tcp_serial_redirect.main()
    except KeyboardInterrupt:
        print("\n🛑 网桥已停止")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        input("按回车键退出...")

if __name__ == "__main__":
    main()