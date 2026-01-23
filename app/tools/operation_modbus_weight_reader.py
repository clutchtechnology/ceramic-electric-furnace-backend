# ============================================================
# 文件说明: modbus_weight_reader.py - 料仓净重 Modbus RTU 读取工具
# ============================================================
# 功能:
#   1. 通过串口发送 Modbus RTU 报文读取料仓净重
#   2. 解析响应报文，计算净重值
#   3. 提供简洁的工具函数供其他模块调用
# ============================================================
# 报文格式 (根据手册):
#   TX: 01 03 00 02 00 02 65 CB
#       01    - 从站地址
#       03    - 功能码 (读取保持寄存器)
#       00 02 - 起始寄存器 (40003)
#       00 02 - 读取数量 (2个寄存器)
#       65 CB - CRC16
#
#   RX: 01 03 04 00 00 01 22 7B BA
#       01    - 从站地址
#       03    - 功能码
#       04    - 数据字节数 (4 bytes)
#       00 00 - 高位 WORD (HIGH)
#       01 22 - 低位 WORD (LOW) = 0x0122 = 290
#       7B BA - CRC16
#
#   净重计算: (HIGH << 16) | LOW = 290 kg
# ============================================================

import struct
import logging
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ============================================================
# CRC16 Modbus 计算
# ============================================================
def calc_crc16(data: bytes) -> int:
    """计算 Modbus RTU CRC16 校验码
    
    Args:
        data: 待校验的字节数据 (不含 CRC)
        
    Returns:
        CRC16 值 (低位在前)
    """
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc


def build_read_request(slave_addr: int = 1, 
                       start_reg: int = 2, 
                       reg_count: int = 2) -> bytes:
    """构建 Modbus RTU 读取请求报文
    
    Args:
        slave_addr: 从站地址 (默认 1)
        start_reg: 起始寄存器地址 (默认 2 = 40003)
        reg_count: 读取寄存器数量 (默认 2)
        
    Returns:
        完整的请求报文 (含 CRC)
    """
    # 构建报文体
    request = struct.pack('>BBHH', slave_addr, 0x03, start_reg, reg_count)
    # 计算 CRC (低位在前)
    crc = calc_crc16(request)
    request += struct.pack('<H', crc)
    return request


def parse_weight_response(response: bytes) -> Tuple[bool, Optional[int], Optional[str]]:
    """解析 Modbus RTU 净重响应报文
    
    Args:
        response: 接收到的响应报文
        
    Returns:
        (success, weight, error_message)
        - success: 解析是否成功
        - weight: 净重值 (单位: kg)，失败时为 None
        - error_message: 错误信息，成功时为 None
    """
    # 最小响应长度: 地址(1) + 功能码(1) + 字节数(1) + 数据(4) + CRC(2) = 9
    if len(response) < 9:
        return False, None, f"响应长度不足: {len(response)} < 9"
    
    # 解析报文头
    slave_addr = response[0]
    func_code = response[1]
    
    # 检查异常响应
    if func_code & 0x80:
        error_code = response[2]
        error_map = {
            0x01: "非法功能码",
            0x02: "非法数据地址",
            0x03: "非法数据值",
            0x04: "从站设备故障"
        }
        return False, None, f"Modbus 异常: {error_map.get(error_code, f'未知错误 {error_code}')}"
    
    # 检查功能码
    if func_code != 0x03:
        return False, None, f"功能码错误: 期望 0x03, 实际 0x{func_code:02X}"
    
    # 获取数据字节数
    byte_count = response[2]
    if byte_count != 4:
        return False, None, f"数据字节数错误: 期望 4, 实际 {byte_count}"
    
    # 验证 CRC
    data_without_crc = response[:-2]
    received_crc = struct.unpack('<H', response[-2:])[0]
    calculated_crc = calc_crc16(data_without_crc)
    if received_crc != calculated_crc:
        return False, None, f"CRC 校验失败: 期望 0x{calculated_crc:04X}, 实际 0x{received_crc:04X}"
    
    # 解析净重数据 (高位在前, 大端序)
    # data[3:5] = HIGH word, data[5:7] = LOW word
    high_word = struct.unpack('>H', response[3:5])[0]
    low_word = struct.unpack('>H', response[5:7])[0]
    
    # 组合为 32 位值
    weight = (high_word << 16) | low_word
    
    return True, weight, None


# ============================================================
# 串口读取函数
# ============================================================
def read_hopper_weight(port: str = "COM1",
                       baudrate: int = 19200,
                       slave_addr: int = 1,
                       timeout: float = 1.0) -> Dict[str, Any]:
    """通过串口读取料仓净重
    
    Args:
        port: 串口号 (Windows: COM1, Linux: /dev/ttyUSB0)
        baudrate: 波特率 (默认 19200)
        slave_addr: Modbus 从站地址 (默认 1)
        timeout: 超时时间 (秒)
        
    Returns:
        {
            "success": bool,
            "weight": int,        # 净重 (kg)
            "unit": "kg",
            "raw_response": bytes,
            "error": str or None
        }
    """
    try:
        import serial
    except ImportError:
        return {
            "success": False,
            "weight": None,
            "unit": "kg",
            "raw_response": None,
            "error": "pyserial 未安装，请运行: pip install pyserial"
        }
    
    result = {
        "success": False,
        "weight": None,
        "unit": "kg",
        "raw_response": None,
        "error": None
    }
    
    try:
        # 记录连接类型 (本地 COM 或 远程 TCP)
        conn_type = "远程 TCP 网桥" if "socket://" in port else "本地串口"
        logger.debug(f"正在连接 {conn_type}: {port} @ {baudrate}")

        # 打开串口 (PySerial 自动处理 socket:// URL)
        ser = serial.serial_for_url(
            url=port,
            baudrate=baudrate,
            bytesize=8,
            parity='E',      # 偶校验
            stopbits=1,
            timeout=timeout,
            do_not_open=True 
        )
        ser.open() # 手动打开以捕获更详细错误
        
        # 构建并发送请求
        request = build_read_request(slave_addr=slave_addr, start_reg=2, reg_count=2)
        logger.debug(f"TX: {request.hex(' ').upper()}")
        ser.write(request)
        
        # 读取响应 (期望 9 字节)
        response = ser.read(9)
        result["raw_response"] = response
        logger.debug(f"RX: {response.hex(' ').upper()}")
        
        # 关闭串口
        ser.close()
        
        if not response:
            result["error"] = "无响应 (超时)"
            return result
        
        # 解析响应
        success, weight, error = parse_weight_response(response)
        result["success"] = success
        result["weight"] = weight
        result["error"] = error
        
    except serial.SerialException as e:
        result["error"] = f"串口错误: {e}"
    except Exception as e:
        result["error"] = f"读取异常: {e}"
    
    return result


# ============================================================
# 便捷函数
# ============================================================
def get_net_weight(port: str = "COM1") -> Optional[int]:
    """快速获取净重值
    
    Args:
        port: 串口号
        
    Returns:
        净重值 (kg)，失败返回 None
    """
    result = read_hopper_weight(port=port)
    if result["success"]:
        return result["weight"]
    else:
        logger.warning(f"读取净重失败: {result['error']}")
        return None


def parse_response_hex(hex_string: str) -> Tuple[bool, Optional[int], Optional[str]]:
    """解析十六进制响应字符串 (用于调试/测试)
    
    Args:
        hex_string: 十六进制字符串, 如 "01 03 04 00 00 01 22 7B BA"
        
    Returns:
        (success, weight, error)
    """
    # 移除空格并转换为 bytes
    hex_clean = hex_string.replace(' ', '').replace('-', '')
    try:
        response = bytes.fromhex(hex_clean)
        return parse_weight_response(response)
    except ValueError as e:
        return False, None, f"十六进制解析失败: {e}"


# ============================================================
# Mock 函数 (用于无硬件环境测试)
# ============================================================
def mock_read_weight(weight: int = 290) -> Dict[str, Any]:
    """模拟读取净重 (用于测试)
    
    Args:
        weight: 模拟的净重值
        
    Returns:
        与 read_hopper_weight() 相同格式的结果
    """
    # 构造模拟响应
    high_word = (weight >> 16) & 0xFFFF
    low_word = weight & 0xFFFF
    
    # 报文: 01 03 04 [HIGH_H HIGH_L] [LOW_H LOW_L] [CRC_L CRC_H]
    data = struct.pack('>BBBHH', 0x01, 0x03, 0x04, high_word, low_word)
    crc = calc_crc16(data)
    response = data + struct.pack('<H', crc)
    
    return {
        "success": True,
        "weight": weight,
        "unit": "kg",
        "raw_response": response,
        "error": None
    }


# ============================================================
# 测试代码
# ============================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(message)s')
    
    print("=" * 60)
    print("料仓净重 Modbus RTU 读取工具 - 测试")
    print("=" * 60)
    
    # 1. 测试报文构建
    print("\n📤 请求报文:")
    request = build_read_request(slave_addr=1, start_reg=2, reg_count=2)
    print(f"   {request.hex(' ').upper()}")
    print(f"   期望: 01 03 00 02 00 02 65 CB")
    
    # 2. 测试响应解析 (使用你提供的真实响应)
    print("\n📥 响应解析测试:")
    test_response = "01 03 04 00 00 01 22 7B BA"
    success, weight, error = parse_response_hex(test_response)
    print(f"   输入: {test_response}")
    print(f"   解析: success={success}, weight={weight} kg, error={error}")
    
    # 3. Mock 测试
    print("\n🧪 Mock 测试:")
    mock_result = mock_read_weight(350)
    print(f"   模拟净重: {mock_result['weight']} kg")
    print(f"   响应报文: {mock_result['raw_response'].hex(' ').upper()}")
    
    # 4. 验证 mock 响应可以被正确解析
    success2, weight2, _ = parse_weight_response(mock_result['raw_response'])
    print(f"   反解析: {weight2} kg (验证{'通过' if weight2 == 350 else '失败'})")
    
    print("\n" + "=" * 60)
    print("💡 实际使用示例:")
    print("   from app.tools.modbus_weight_reader import read_hopper_weight")
    print("   result = read_hopper_weight(port='COM1')")
    print("   if result['success']:")
    print("       print(f\"净重: {result['weight']} kg\")")
    print("=" * 60)
