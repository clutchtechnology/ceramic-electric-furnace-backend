# ============================================================
# 文件说明: converter_valve.py - 蝶阀控制转换器
# ============================================================
# 功能:
#   1. 读取蝶阀状态 (OPEN/CLOSE/BUSY)
#   2. 写入蝶阀控制命令 (开/关/暂停)
#   3. 支持单个或批量蝶阀操作
# 
# 硬件配置:
#   - ValveControl 模块 (DB32, offset 20-27): 状态读取
#     - OPEN (bit 0): 开阀状态
#     - CLOSE (bit 1): 关阀状态
#     - BUSY (bit 2): 忙碌/运行中状态
#   - MBrly 写入数组 (DB32, offset 28): 控制写入
#     - Array[0..7] of Bool: 8个继电器控制位
# 
# 控制逻辑说明:
#   - 蝶阀控制通常采用**脉冲控制**方式
#   - 开阀: 向对应继电器发送脉冲信号 (True -> 延时 -> False)
#   - 关阀: 向另一个继电器发送脉冲信号
#   - 暂停: 清除所有控制信号 (两个继电器都置 False)
#   
# 注意:
#   - 具体的继电器分配需要与 PLC 程序对应
#   - 典型配置: 一个蝶阀对应 2 个继电器 (开阀/关阀)
#   - MBrly[0]=开阀1, MBrly[1]=关阀1, MBrly[2]=开阀2, MBrly[3]=关阀2 ...
# ============================================================

from typing import Dict, Any, Optional, Tuple, List
from enum import Enum
import struct
import time


class ValveAction(Enum):
    """蝶阀操作类型"""
    OPEN = "open"       # 开阀
    CLOSE = "close"     # 关阀
    STOP = "stop"       # 暂停/停止


class ValveState(Enum):
    """蝶阀状态"""
    OPEN = "open"           # 全开
    CLOSE = "closed"        # 全关
    BUSY = "busy"           # 运行中 (正在开/关)
    FAULT = "fault"         # 故障
    UNKNOWN = "unknown"     # 未知


class ValveConverter:
    """蝶阀控制转换器"""
    
    # 默认配置
    DEFAULT_DB_NUMBER = 32
    STATUS_OFFSET = 20       # ValveControl 起始偏移
    CONTROL_OFFSET = 28      # MBrly 写入偏移
    
    # 每组 ValveControl 占 2 字节
    VALVE_CONTROL_SIZE = 2
    
    # 蝶阀数量配置
    TOTAL_VALVES = 8         # 总共 8 个蝶阀
    RELAYS_PER_VALVE = 2     # 每个蝶阀使用 2 个继电器 (开/关)
    
    def __init__(self, db_number: int = None):
        """初始化蝶阀转换器
        
        Args:
            db_number: DB 块号，默认 32
        """
        self.db_number = db_number or self.DEFAULT_DB_NUMBER
    
    # ==================== 状态解析 ====================
    
    @staticmethod
    def parse_valve_status(raw_word: int) -> Dict[str, Any]:
        """解析单个蝶阀状态 (从 ValveControl WORD)
        
        Args:
            raw_word: 原始 WORD 值 (2 bytes)
            
        Returns:
            包含 open, close, busy 状态的字典
        """
        is_open = bool(raw_word & 0x01)     # bit 0
        is_close = bool(raw_word & 0x02)    # bit 1
        is_busy = bool(raw_word & 0x04)     # bit 2
        
        # 判断综合状态
        if is_busy:
            state = ValveState.BUSY
        elif is_open and not is_close:
            state = ValveState.OPEN
        elif is_close and not is_open:
            state = ValveState.CLOSE
        elif is_open and is_close:
            state = ValveState.FAULT  # 同时开和关是故障
        else:
            state = ValveState.UNKNOWN
        
        return {
            'open': is_open,
            'close': is_close,
            'busy': is_busy,
            'state': state.value,
            'raw': raw_word
        }
    
    @staticmethod
    def parse_all_valve_status(data: bytes, offset: int = 20) -> Dict[str, Any]:
        """解析所有蝶阀状态
        
        Args:
            data: DB32 原始数据 (至少 28 bytes)
            offset: ValveControl 起始偏移量
            
        Returns:
            包含 4 组 (8个蝶阀) 状态的字典
        """
        if len(data) < offset + 8:
            return {'error': f'数据长度不足: 需要 {offset + 8} bytes, 实际 {len(data)} bytes'}
        
        result = {}
        valve_names = ['Ctrl_1', 'Ctrl_2', 'Ctrl_3', 'Ctrl_4']
        
        for i, name in enumerate(valve_names):
            word_offset = offset + i * 2
            raw_word = struct.unpack('>H', data[word_offset:word_offset + 2])[0]
            result[name] = ValveConverter.parse_valve_status(raw_word)
            
            # 添加对应的蝶阀编号
            valve_idx_start = i * 2 + 1
            result[name]['valves'] = [valve_idx_start, valve_idx_start + 1]
        
        return result
    
    # ==================== 控制命令生成 ====================
    
    @staticmethod
    def generate_control_byte(
        valve_id: int, 
        action: ValveAction,
        current_byte: int = 0x00
    ) -> int:
        """生成单个蝶阀的控制字节
        
        Args:
            valve_id: 蝶阀编号 (1-8)
            action: 操作类型 (OPEN/CLOSE/STOP)
            current_byte: 当前 MBrly 字节值
            
        Returns:
            更新后的控制字节
        
        注意:
            继电器分配 (假设配置):
            - 蝶阀1: MBrly[0]=开, MBrly[1]=关 (实际需要根据 PLC 程序调整)
            - 蝶阀2: MBrly[2]=开, MBrly[3]=关
            - 蝶阀3: MBrly[4]=开, MBrly[5]=关
            - 蝶阀4: MBrly[6]=开, MBrly[7]=关
        """
        if not 1 <= valve_id <= 4:
            raise ValueError(f"蝶阀编号必须在 1-4 之间, 收到: {valve_id}")
        
        # 计算对应的 bit 位置
        open_bit = (valve_id - 1) * 2      # 开阀 bit
        close_bit = (valve_id - 1) * 2 + 1 # 关阀 bit
        
        open_mask = 1 << open_bit
        close_mask = 1 << close_bit
        
        if action == ValveAction.OPEN:
            # 开阀: 设置开阀位, 清除关阀位
            current_byte = (current_byte | open_mask) & ~close_mask
        elif action == ValveAction.CLOSE:
            # 关阀: 清除开阀位, 设置关阀位
            current_byte = (current_byte & ~open_mask) | close_mask
        elif action == ValveAction.STOP:
            # 暂停: 清除开阀位和关阀位
            current_byte = current_byte & ~open_mask & ~close_mask
        
        return current_byte
    
    @staticmethod
    def generate_all_stop_byte() -> int:
        """生成全部暂停的控制字节
        
        Returns:
            0x00 (所有继电器关闭)
        """
        return 0x00
    
    # ==================== 高级控制功能 ====================
    
    def create_valve_command(
        self,
        valve_id: int,
        action: ValveAction
    ) -> Dict[str, Any]:
        """创建蝶阀控制命令包
        
        Args:
            valve_id: 蝶阀编号 (1-4)
            action: 操作类型
            
        Returns:
            包含控制信息的字典
        """
        control_byte = self.generate_control_byte(valve_id, action)
        
        return {
            'db_number': self.db_number,
            'offset': self.CONTROL_OFFSET,
            'data': bytes([control_byte]),
            'size': 1,
            'valve_id': valve_id,
            'action': action.value,
            'control_byte': f'0x{control_byte:02X}',
            'binary': format(control_byte, '08b')
        }
    
    def create_batch_command(
        self,
        commands: List[Tuple[int, ValveAction]]
    ) -> Dict[str, Any]:
        """创建批量蝶阀控制命令
        
        Args:
            commands: [(valve_id, action), ...] 列表
            
        Returns:
            包含合并控制信息的字典
        """
        control_byte = 0x00
        
        for valve_id, action in commands:
            control_byte = self.generate_control_byte(
                valve_id, action, control_byte
            )
        
        return {
            'db_number': self.db_number,
            'offset': self.CONTROL_OFFSET,
            'data': bytes([control_byte]),
            'size': 1,
            'commands': [(vid, act.value) for vid, act in commands],
            'control_byte': f'0x{control_byte:02X}',
            'binary': format(control_byte, '08b')
        }


# ==================== 便捷函数 ====================

def parse_valve_status(raw_word: int) -> Dict[str, Any]:
    """解析蝶阀状态 (便捷函数)"""
    return ValveConverter.parse_valve_status(raw_word)


def parse_all_valves(data: bytes, offset: int = 20) -> Dict[str, Any]:
    """解析所有蝶阀状态 (便捷函数)"""
    return ValveConverter.parse_all_valve_status(data, offset)


def create_open_command(valve_id: int) -> Dict[str, Any]:
    """创建开阀命令 (便捷函数)"""
    converter = ValveConverter()
    return converter.create_valve_command(valve_id, ValveAction.OPEN)


def create_close_command(valve_id: int) -> Dict[str, Any]:
    """创建关阀命令 (便捷函数)"""
    converter = ValveConverter()
    return converter.create_valve_command(valve_id, ValveAction.CLOSE)


def create_stop_command(valve_id: int) -> Dict[str, Any]:
    """创建暂停命令 (便捷函数)"""
    converter = ValveConverter()
    return converter.create_valve_command(valve_id, ValveAction.STOP)


def create_all_stop_command() -> Dict[str, Any]:
    """创建全部暂停命令 (便捷函数)"""
    return {
        'db_number': 32,
        'offset': 28,
        'data': bytes([0x00]),
        'size': 1,
        'action': 'all_stop',
        'control_byte': '0x00',
        'binary': '00000000'
    }


# ==================== 测试代码 ====================

if __name__ == "__main__":
    print("=" * 60)
    print("蝶阀控制转换器测试")
    print("=" * 60)
    
    # 1. 状态解析测试
    print("\n【1. 状态解析测试】")
    test_cases = [
        (0x01, "全开"),
        (0x02, "全关"),
        (0x04, "运行中"),
        (0x05, "开+运行中"),
        (0x03, "开+关 (故障)"),
        (0x00, "未知"),
    ]
    
    for raw, desc in test_cases:
        result = parse_valve_status(raw)
        print(f"  原始值: 0x{raw:02X} ({desc})")
        print(f"    -> 状态: {result['state']}, open={result['open']}, close={result['close']}, busy={result['busy']}")
    
    # 2. 控制命令生成测试
    print("\n【2. 控制命令生成测试】")
    
    # 开阀命令
    cmd = create_open_command(1)
    print(f"  蝶阀1 开阀: {cmd['control_byte']} ({cmd['binary']})")
    
    cmd = create_close_command(1)
    print(f"  蝶阀1 关阀: {cmd['control_byte']} ({cmd['binary']})")
    
    cmd = create_stop_command(1)
    print(f"  蝶阀1 暂停: {cmd['control_byte']} ({cmd['binary']})")
    
    cmd = create_open_command(2)
    print(f"  蝶阀2 开阀: {cmd['control_byte']} ({cmd['binary']})")
    
    cmd = create_open_command(3)
    print(f"  蝶阀3 开阀: {cmd['control_byte']} ({cmd['binary']})")
    
    cmd = create_open_command(4)
    print(f"  蝶阀4 开阀: {cmd['control_byte']} ({cmd['binary']})")
    
    # 3. 批量命令测试
    print("\n【3. 批量命令测试】")
    converter = ValveConverter()
    
    batch_cmd = converter.create_batch_command([
        (1, ValveAction.OPEN),
        (2, ValveAction.CLOSE),
        (3, ValveAction.OPEN),
    ])
    print(f"  蝶阀1开 + 蝶阀2关 + 蝶阀3开:")
    print(f"    控制字节: {batch_cmd['control_byte']} ({batch_cmd['binary']})")
    
    # 4. 全停命令
    print("\n【4. 全部暂停命令】")
    cmd = create_all_stop_command()
    print(f"  全部暂停: {cmd['control_byte']} ({cmd['binary']})")
    
    # 5. 模拟解析 DB32 数据
    print("\n【5. 模拟解析完整 DB32 数据】")
    # 模拟 29 字节数据 (Ctrl_1 到 Ctrl_4 在 offset 20-27)
    # 注意: S7-1200 使用大端序 (Big Endian)
    mock_data = bytes([
        0x00] * 20 +  # 前 20 字节
        [0x00, 0x01,  # Ctrl_1: 蝶阀1 全开 (大端: 0x0001)
         0x00, 0x02,  # Ctrl_2: 蝶阀3 全关 (大端: 0x0002)
         0x00, 0x04,  # Ctrl_3: 蝶阀5 运行中 (大端: 0x0004)
         0x00, 0x00,  # Ctrl_4: 蝶阀7 未知 (大端: 0x0000)
         0x00]        # MBrly
    )
    
    all_status = parse_all_valves(mock_data)
    for name, status in all_status.items():
        print(f"  {name}: 状态={status['state']}, 对应蝶阀={status.get('valves', 'N/A')}")
    
    print("\n" + "=" * 60)
    print("✅ 蝶阀控制转换器测试完成")
    print("=" * 60)
    print("""
📋 使用说明:
-----------
1. 开阀:   create_open_command(valve_id)  -> valve_id: 1-4
2. 关阀:   create_close_command(valve_id) -> valve_id: 1-4
3. 暂停:   create_stop_command(valve_id)  -> valve_id: 1-4
4. 全停:   create_all_stop_command()

示例:
    from app.tools.converter_valve import create_open_command
    cmd = create_open_command(1)
    plc_manager.write_db(cmd['db_number'], cmd['offset'], cmd['data'])
""")
