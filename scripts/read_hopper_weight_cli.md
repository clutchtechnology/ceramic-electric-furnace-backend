# 独立测试脚本：读取料仓称重 (Modbus RTU)

此脚本 (`read_hopper_weight.py`) 用于直接测试串口通信，验证是否能从 PLC/仪表读取到料仓重量数据。
可以在 **工控机直接运行** (需要安装 Python 和 pyserial)。

## 1. 脚本代码 (`scripts/read_hopper_weight.py`)

已创建脚本文件 `read_hopper_weight.py`。其配置如下：

```python
import serial
import struct
import time
import sys

# ============================================================
# 配置参数
# ============================================================
PORT = "COM1"           # 串口号 (Windows: COM1, Linux: /dev/ttyUSB0)
BAUDRATE = 19200        # 波特率
TIMEOUT = 1.0           # 超时时间 (秒)
SLAVE_ADDR = 1          # 从站地址

# ============================================================
# CRC16 相关函数
# ============================================================
def calc_crc16(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc

def build_read_request(slave_addr: int = 1, start_reg: int = 2, reg_count: int = 2) -> bytes:
    # 03 功能码读取保持寄存器
    # 40003 对应起始地址 2 (0-based)
    request = struct.pack('>BBHH', slave_addr, 0x03, start_reg, reg_count)
    crc = calc_crc16(request)
    request += struct.pack('<H', crc)
    return request

# ============================================================
# 主逻辑
# ============================================================
def main():
    print(f"Opening Serial Port: {PORT} @ {BAUDRATE}...")
    
    try:
        ser = serial.Serial(
            port=PORT,
            baudrate=BAUDRATE,
            bytesize=8,
            parity='E',  # Even parity (偶校验)
            stopbits=1,
            timeout=TIMEOUT
        )
    except serial.SerialException as e:
        print(f"❌ 打开串口失败: {e}")
        print("提示: 如果在 Docker 中运行，容器通常无法直接访问宿主机 COM 口。")
        print("      请直接在 Windows 宿主机上运行此脚本。")
        sys.exit(1)

    if ser.is_open:
        print(f"✅ 串口已打开: {ser.name}")

    try:
        # 构建请求: 01 03 00 02 00 02 [CRC-L] [CRC-H]
        req = build_read_request(SLAVE_ADDR, 2, 2)
        print(f"\nTX >>> {req.hex(' ').upper()}")
        
        ser.write(req)
        time.sleep(0.1)
        
        # 响应通常是 9 字节: Addr(1) + Func(1) + Len(1) + Data(4) + CRC(2)
        resp = ser.read(9)
        print(f"RX <<< {resp.hex(' ').upper()}")
        
        if not resp:
            print("❌ 读取超时 (No Response)")
            return

        if len(resp) < 9:
            print(f"❌ 响应不完整 (Length: {len(resp)})")
            return

        # 简单校验
        if resp[0] != SLAVE_ADDR:
            print(f"❌ 地址不匹配 (Expected: {SLAVE_ADDR}, Got: {resp[0]})")
            return
            
        if resp[1] != 0x03:
            print(f"❌ 功能码错误 (Expected: 03, Got: {resp[1]:02X})")
            if resp[1] & 0x80:
                 print(f"   (异常码: {resp[2]:02X})")
            return

        # 解析数据
        # Data is at index 3..6 (4 bytes) -> High Word, Low Word
        # Big Endian
        high_word = struct.unpack('>H', resp[3:5])[0]
        low_word = struct.unpack('>H', resp[5:7])[0]
        
        # 32位组合
        weight_raw = (high_word << 16) | low_word
        
        print("\n================ Results ================")
        print(f"High Word: {high_word}")
        print(f"Low Word : {low_word}")
        print(f"Weight   : {weight_raw} kg")
        print("=========================================")

    except Exception as e:
        print(f"❌ 通信错误: {e}")
    finally:
        ser.close()
        print("\n串口已关闭")

if __name__ == "__main__":
    main()
```

## 2. 运行方法

**推荐: 在 Windows 宿主机直接运行** 

1. 确保安装 python 和 pyserial
   ```powershell
   pip install pyserial
   ```
2. 保存代码为 `read_hopper_weight.py`
3. 运行:
   ```powershell
   python read_hopper_weight.py
   ```

**如果在 Docker 容器内调试 (通常不通):**

```bash
docker exec -it furnace-backend python /app/scripts/read_hopper_weight.py
```
> 注意: 除非使用了特殊手段(如 --device 映射 Linux 设备)，否则 Win Docker 容器无法访问 COM1。
