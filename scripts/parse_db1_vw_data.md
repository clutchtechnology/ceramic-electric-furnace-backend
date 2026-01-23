cd D:\furnace-backend
venv\Scripts\python -c "
import struct
import sys
sys.path.insert(0, '.')
from app.plc.plc_manager import get_plc_manager

# ============================================================
# DB1 字段映射表 (offset -> (字段名, 类型, 单位, 描述))
# ============================================================
FIELD_MAP = {
    # 电机输出
    0: ('motor_output_1', 'INT', '', '第一路电机输出'),
    2: ('motor_output_spare', 'INT', '', '备用电机输出'),
    4: ('motor_output_2', 'INT', '', '第二路电机输出'),
    6: ('motor_output_3', 'INT', '', '第三路电机输出'),
    
    # ============================================================
    # ⭐⭐⭐ UVW 三相弧流弧压 (实际使用的数据, offset 10-24) ⭐⭐⭐
    # ============================================================
    10: ('arc_current_U', 'INT', 'A', '⭐⭐ U相弧流 (实际)'),
    12: ('arc_voltage_U', 'INT', 'V', '⭐⭐ U相弧压 (实际)'),
    14: ('Vw14', 'INT', '', 'Vw14'),
    16: ('arc_current_V', 'INT', 'A', '⭐⭐ V相弧流 (实际)'),
    18: ('arc_voltage_V', 'INT', 'V', '⭐⭐ V相弧压 (实际)'),
    20: ('Vw20', 'INT', '', 'Vw20'),
    22: ('arc_current_W', 'INT', 'A', '⭐⭐ W相弧流 (实际)'),
    24: ('arc_voltage_W', 'INT', 'V', '⭐⭐ W相弧压 (实际)'),
    
    # ⭐ 弧流设定值 (重要)
    32: ('arc_current_setpoint_U', 'INT', 'A', '⭐ U相弧流设定值'),
    34: ('arc_sensitivity_U', 'INT', '', 'U相弧流自动灵敏度'),
    36: ('arc_current_setpoint_V', 'INT', 'A', '⭐ V相弧流设定值'),
    38: ('arc_sensitivity_V', 'INT', '', 'V相弧流自动灵敏度'),
    40: ('arc_current_setpoint_W', 'INT', 'A', '⭐ W相弧流设定值'),
    42: ('arc_sensitivity_W', 'INT', '', 'W相弧流自动灵敏度'),
    
    # ⭐ 死区设置 (重要)
    48: ('manual_deadzone_percent', 'INT', '%', '⭐ 手动死区百分比'),
    64: ('arc_current_deadzone_lower', 'INT', 'A', '⭐ 弧流死区下限'),
    66: ('arc_current_deadzone_upper', 'INT', 'A', '⭐ 弧流死区上限'),
    
    # 弧流弧压 A相 (offset 94-105) - PLC内部数据，前端不使用
    94: ('arc_current_A_normalized', 'REAL', '', 'A相弧流归一化(内部)'),
    98: ('arc_current_A_scale', 'INT', 'A', 'A相弧流比例放大(内部)'),
    100: ('arc_voltage_A_normalized', 'REAL', '', 'A相弧压归一化(内部)'),
    104: ('arc_voltage_A_scale', 'INT', 'V', 'A相弧压比例放大(内部)'),
    
    # 弧流弧压 B相 (offset 106-117) - PLC内部数据，前端不使用
    106: ('arc_current_B_normalized', 'REAL', '', 'B相弧流归一化(内部)'),
    110: ('arc_current_B_scale', 'INT', 'A', 'B相弧流比例放大(内部)'),
    112: ('arc_voltage_B_normalized', 'REAL', '', 'B相弧压归一化(内部)'),
    116: ('arc_voltage_B_scale', 'INT', 'V', 'B相弧压比例放大(内部)'),
    
    # 弧流弧压 C相 (offset 118-129) - PLC内部数据，前端不使用
    118: ('arc_current_C_normalized', 'REAL', '', 'C相弧流归一化(内部)'),
    122: ('arc_current_C_scale', 'INT', 'A', 'C相弧流比例放大(内部)'),
    124: ('arc_voltage_C_normalized', 'REAL', '', 'C相弧压归一化(内部)'),
    128: ('arc_voltage_C_scale', 'INT', 'V', 'C相弧压比例放大(内部)'),
    
    # 备用相 (offset 130-141)
    130: ('arc_current_spare_normalized', 'REAL', '', '备用相弧流归一化'),
    134: ('arc_current_spare_scale', 'INT', 'A', '备用相弧流'),
    136: ('arc_voltage_spare_normalized', 'REAL', '', '备用相弧压归一化'),
    140: ('arc_voltage_spare_scale', 'INT', 'V', '备用相弧压'),
    
    # 弧流给定 (offset 142-147)
    142: ('arc_current_setpoint_normalized', 'REAL', '', '弧流给定归一化'),
    146: ('arc_current_setpoint_scale', 'INT', 'A', '弧流给定比例'),
    
    # 变频电机电流 (offset 148-165)
    148: ('vfd_motor_current_A_normalized', 'REAL', '', 'U相变频电机电流归一化'),
    152: ('vfd_motor_current_A_scale', 'INT', 'A', 'U相变频电机电流'),
    154: ('vfd_motor_current_B_normalized', 'REAL', '', 'V相变频电机电流归一化'),
    158: ('vfd_motor_current_B_scale', 'INT', 'A', 'V相变频电机电流'),
    160: ('vfd_motor_current_C_normalized', 'REAL', '', 'W相变频电机电流归一化'),
    164: ('vfd_motor_current_C_scale', 'INT', 'A', 'W相变频电机电流'),
    
    # 电机输出归一化 (offset 166-181)
    166: ('motor_output_1_normalized', 'REAL', '', '第一路电机输出归一化'),
    170: ('motor_output_spare_normalized', 'REAL', '', '备用电机输出归一化'),
    174: ('motor_output_2_normalized', 'REAL', '', '第二路电机输出归一化'),
    178: ('motor_output_3_normalized', 'REAL', '', '第三路电机输出归一化'),
}

# 重要字段（高亮显示）- 使用实际的 offset 10-24 弧流弧压
IMPORTANT_OFFSETS = {10, 12, 16, 18, 22, 24, 32, 36, 40, 48, 64, 66}

plc = get_plc_manager()
data, err = plc.read_db(1, 0, 182)

if data:
    data = bytes(data)
    print('=== DB1 Full Raw Data (182 bytes) ===')
    print()
    
    # ============================================================
    # 1. 打印所有数据（INT格式，带字段注释）
    # ============================================================
    print('--- All Data as INT (Big Endian) ---')
    for i in range(0, 182, 2):
        val = struct.unpack('>h', data[i:i+2])[0]
        hex_str = data[i:i+2].hex().upper()
        
        # 获取字段信息
        field_info = FIELD_MAP.get(i)
        if field_info:
            name, dtype, unit, desc = field_info
            unit_str = f' {unit}' if unit else ''
            
            # 高亮重要字段
            if i in IMPORTANT_OFFSETS:
                marker = '★' if val != 0 else '☆'
                print(f'  [{i:3d}-{i+1:3d}]: {hex_str} = {val:6d}{unit_str:3s}  {marker} {desc}')
            else:
                marker = '<-- NON-ZERO!' if val != 0 else ''
                print(f'  [{i:3d}-{i+1:3d}]: {hex_str} = {val:6d}{unit_str:3s}  {marker:15s} # {desc}')
        else:
            marker = '<-- NON-ZERO!' if val != 0 else ''
            print(f'  [{i:3d}-{i+1:3d}]: {hex_str} = {val:6d}  {marker}')
    
    # ============================================================
    # 2. 重要字段汇总（弧流弧压 + 设定值 + 死区）
    # ============================================================
    print()
    print('=' * 60)
    print('⭐ 重要字段汇总 (弧流弧压 + 设定值 + 死区)')
    print('=' * 60)
    
    # 弧流设定值
    setpoint_U = struct.unpack('>h', data[32:34])[0]
    setpoint_V = struct.unpack('>h', data[36:38])[0]
    setpoint_W = struct.unpack('>h', data[40:42])[0]
    print(f'  弧流设定值:')
    print(f'    U相: {setpoint_U} A (offset 32)')
    print(f'    V相: {setpoint_V} A (offset 36)')
    print(f'    W相: {setpoint_W} A (offset 40)')
    
    # 死区
    deadzone_pct = struct.unpack('>h', data[48:50])[0]
    deadzone_lower = struct.unpack('>h', data[64:66])[0]
    deadzone_upper = struct.unpack('>h', data[66:68])[0]
    print(f'  死区设置:')
    print(f'    手动死区: {deadzone_pct}% (offset 48)')
    print(f'    死区下限: {deadzone_lower} A (offset 64)')
    print(f'    死区上限: {deadzone_upper} A (offset 66)')
    
    # ⭐⭐ UVW 三相弧流弧压实际值 (正确的 offset 10-24)
    arc_I_U = struct.unpack('>h', data[10:12])[0]
    arc_V_U = struct.unpack('>h', data[12:14])[0]
    arc_I_V = struct.unpack('>h', data[16:18])[0]
    arc_V_V = struct.unpack('>h', data[18:20])[0]
    arc_I_W = struct.unpack('>h', data[22:24])[0]
    arc_V_W = struct.unpack('>h', data[24:26])[0]
    print(f'  弧流弧压实际值 (offset 10-24):')
    print(f'    U相: 弧流 {arc_I_U} A (offset 10), 弧压 {arc_V_U} V (offset 12)')
    print(f'    V相: 弧流 {arc_I_V} A (offset 16), 弧压 {arc_V_V} V (offset 18)')
    print(f'    W相: 弧流 {arc_I_W} A (offset 22), 弧压 {arc_V_W} V (offset 24)')
    
    # 计算报警状态
    print()
    print('--- 报警计算 (基于设定值 ± 死区%) ---')
    for phase, (setpoint, current) in [('U', (setpoint_U, arc_I_U)), 
                                         ('V', (setpoint_V, arc_I_V)), 
                                         ('W', (setpoint_W, arc_I_W))]:
        if setpoint > 0 and deadzone_pct > 0:
            lower = setpoint * (1 - deadzone_pct / 100.0)
            upper = setpoint * (1 + deadzone_pct / 100.0)
            status = '✅ 正常' if lower <= current <= upper else '❌ 报警'
            print(f'  {phase}相: 设定={setpoint}A, 实际={current}A, 范围=[{lower:.0f}, {upper:.0f}] -> {status}')
        else:
            print(f'  {phase}相: 设定={setpoint}A, 实际={current}A, (无有效死区设置)')
    
    # ============================================================
    # 3. 非零值汇总
    # ============================================================
    print()
    print('--- Non-zero values summary ---')
    for i in range(0, 182, 2):
        val = struct.unpack('>h', data[i:i+2])[0]
        if val != 0:
            field_info = FIELD_MAP.get(i)
            if field_info:
                name, dtype, unit, desc = field_info
                unit_str = f' {unit}' if unit else ''
                print(f'  Offset {i:3d}: {val:6d}{unit_str:3s}  # {desc}')
            else:
                print(f'  Offset {i:3d}: {val:6d}')
    
    # ============================================================
    # 4. Raw hex dump
    # ============================================================
    print()
    print('--- Raw hex dump ---')
    for i in range(0, 182, 16):
        hex_str = data[i:min(i+16, 182)].hex().upper()
        hex_fmt = ' '.join([hex_str[j:j+2] for j in range(0, len(hex_str), 2)])
        print(f'  {i:3d}: {hex_fmt}')
else:
    print(f'Read failed: {err}')
"