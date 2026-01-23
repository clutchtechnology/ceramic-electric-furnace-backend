# ============================================================
# 文件说明: simple_serial_bridge.py - 简单串口转TCP网桥
# ============================================================
# 用法: python simple_serial_bridge.py
# 功能: 将 COM1 串口数据转发到 TCP 7777 端口
# ============================================================

import socket
import serial
import threading
import time
import sys

# 配置参数
SERIAL_PORT = "COM1"
BAUDRATE = 19200
PARITY = serial.PARITY_EVEN
BYTESIZE = 8
STOPBITS = 1
TCP_HOST = "0.0.0.0"
TCP_PORT = 7777

def handle_client(client_socket, ser, client_addr):
    """处理单个客户端连接"""
    print(f"[+] 新连接: {client_addr}")
    
    try:
        while True:
            # 从TCP客户端接收数据
            data = client_socket.recv(1024)
            if not data:
                break
            
            print(f"[TCP->串口] {data.hex(' ').upper()}")
            
            # 转发到串口
            ser.write(data)
            
            # 等待串口响应 (最多1秒)
            time.sleep(0.1)  # 等待设备处理
            
            # 读取串口响应
            response = b''
            start_time = time.time()
            while time.time() - start_time < 1.0:
                if ser.in_waiting > 0:
                    chunk = ser.read(ser.in_waiting)
                    response += chunk
                    time.sleep(0.05)  # 等待更多数据
                else:
                    if response:  # 已收到数据且没有更多
                        break
                    time.sleep(0.01)
            
            if response:
                print(f"[串口->TCP] {response.hex(' ').upper()}")
                client_socket.send(response)
            else:
                print(f"[串口] 无响应")
                
    except Exception as e:
        print(f"[-] 客户端错误: {e}")
    finally:
        client_socket.close()
        print(f"[-] 连接断开: {client_addr}")

def main():
    print("=" * 60)
    print("   串口转TCP网桥 (简单版)")
    print("=" * 60)
    print(f"   串口: {SERIAL_PORT} @ {BAUDRATE} (8E1)")
    print(f"   TCP:  {TCP_HOST}:{TCP_PORT}")
    print("=" * 60)
    
    # 打开串口
    try:
        ser = serial.Serial(
            port=SERIAL_PORT,
            baudrate=BAUDRATE,
            bytesize=BYTESIZE,
            parity=PARITY,
            stopbits=STOPBITS,
            timeout=1
        )
        print(f"[+] 串口 {SERIAL_PORT} 已打开")
    except serial.SerialException as e:
        print(f"[-] 无法打开串口 {SERIAL_PORT}: {e}")
        sys.exit(1)
    
    # 创建TCP服务器
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind((TCP_HOST, TCP_PORT))
        server.listen(5)
        print(f"[+] TCP服务器监听: {TCP_HOST}:{TCP_PORT}")
        print("[*] 等待连接... (Ctrl+C 退出)")
        
        while True:
            client_socket, client_addr = server.accept()
            client_thread = threading.Thread(
                target=handle_client,
                args=(client_socket, ser, client_addr)
            )
            client_thread.daemon = True
            client_thread.start()
            
    except KeyboardInterrupt:
        print("\n[*] 正在关闭...")
    except Exception as e:
        print(f"[-] 服务器错误: {e}")
    finally:
        ser.close()
        server.close()
        print("[*] 已退出")

if __name__ == "__main__":
    main()
