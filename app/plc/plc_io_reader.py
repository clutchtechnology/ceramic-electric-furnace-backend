# ============================================================
# 文件说明: plc_io_reader.py - PLC 输入/输出位读取
# ============================================================
# 功能:
#   1. 读取PLC输出位 (%Q区域)
#   2. 专门用于读取投料相关信号
# ============================================================

from snap7.types import Areas
from typing import Dict, Any
from datetime import datetime


def read_feeding_signals(plc_client) -> Dict[str, Any]:
    """读取投料相关的PLC信号
    
    Args:
        plc_client: Snap7 客户端实例 (plc._client)
        
    Returns:
        {
            'feeding_discharge': bool,  # Q3.7 秤排料 (True=投料中)
            'feeding_request': bool,    # Q4.0 秤要料 (True=加料中)
            'timestamp': datetime
        }
    """
    try:
        # 读取 Q3-Q4 (2个字节)
        q_data = plc_client.read_area(Areas.PA, 0, 3, 2)
        
        # 解析信号
        # Q3.7 = Byte 3, Bit 7 (0x80 = 10000000)
        feeding_discharge = bool(q_data[0] & 0x80)
        
        # Q4.0 = Byte 4, Bit 0 (0x01 = 00000001)
        feeding_request = bool(q_data[1] & 0x01)
        
        return {
            'feeding_discharge': feeding_discharge,
            'feeding_request': feeding_request,
            'timestamp': datetime.now(),
            'success': True,
            'error': None
        }
        
    except Exception as e:
        return {
            'feeding_discharge': False,
            'feeding_request': False,
            'timestamp': datetime.now(),
            'success': False,
            'error': str(e)
        }


def read_output_bits_full(plc_client) -> Dict[str, Any]:
    """读取完整的输出位状态（用于调试）
    
    Returns:
        {
            'Q0': dict,  # Q0.0 - Q0.7
            'Q1': dict,  # Q1.0 - Q1.7
            'Q2': dict,  # Q2.0 - Q2.7
            'Q3': dict,  # Q3.0 - Q3.7
            'Q4': dict,  # Q4.0 - Q4.7
        }
    """
    try:
        # 读取 Q0-Q4 (5个字节)
        q_data = plc_client.read_area(Areas.PA, 0, 0, 5)
        
        result = {}
        for byte_idx in range(5):
            byte_data = q_data[byte_idx]
            byte_dict = {}
            
            for bit_idx in range(8):
                bit_value = bool(byte_data & (1 << bit_idx))
                byte_dict[f'Q{byte_idx}.{bit_idx}'] = bit_value
            
            result[f'Q{byte_idx}'] = byte_dict
        
        return result
        
    except Exception as e:
        return {'error': str(e)}


# ============================================================
# 测试代码
# ============================================================
if __name__ == "__main__":
    import sys
    sys.path.insert(0, '.')
    
    from app.plc.plc_manager import get_plc_manager
    
    print("=" * 70)
    print("PLC 投料信号读取测试")
    print("=" * 70)
    
    # 连接PLC
    plc = get_plc_manager()
    success, msg = plc.connect()
    
    if not success:
        print(f"❌ PLC连接失败: {msg}")
        sys.exit(1)
    
    print("✅ PLC连接成功\n")
    
    # 读取投料信号
    signals = read_feeding_signals(plc._client)
    
    print("投料信号状态:")
    print("-" * 70)
    print(f"  Q3.7 秤排料: {'✓ 投料中' if signals['feeding_discharge'] else '✗ 停止'}")
    print(f"  Q4.0 秤要料: {'✓ 加料中' if signals['feeding_request'] else '✗ 空闲'}")
    print(f"  时间戳: {signals['timestamp']}")
    
    # 读取完整输出位（调试用）
    print("\n完整输出位状态:")
    print("-" * 70)
    full_outputs = read_output_bits_full(plc._client)
    
    for byte_name, byte_data in full_outputs.items():
        if isinstance(byte_data, dict):
            print(f"\n{byte_name}:")
            for bit_name, bit_value in byte_data.items():
                status = "1" if bit_value else "0"
                print(f"  {bit_name}: {status}")
    
    print("\n" + "=" * 70)
