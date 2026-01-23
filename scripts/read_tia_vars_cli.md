
docker exec -it furnace-backend python -c "
import sys, os, struct
sys.path.append(os.getcwd())
from app.plc.plc_manager import get_plc_manager
from snap7.types import Areas

def get_bit(data, byte_idx, bit_idx):
    if byte_idx < len(data): return bool(data[byte_idx] & (1 << bit_idx))
    return False

def get_word(data, offset):
    if offset + 2 <= len(data): return struct.unpack('>h', data[offset:offset+2])[0]
    return 0

try:
    print('Connecting to PLC...')
    plc = get_plc_manager()
    if not plc.connect()[0]:
        print('Connection failed')
        sys.exit(1)
    client = plc._client
    
    print('\n=== 1. 输入位 (Inputs %I0.0 - %I4.7) ===')
    # 读取 5 个字节 (Byte 0-4)
    i_data = client.read_area(Areas.PE, 0, 0, 5)
    
    print(f'I0.0 U相电极自动:   {get_bit(i_data, 0, 0)}')
    print(f'I0.3 升三相启动:    {get_bit(i_data, 0, 3)}')
    print(f'I0.5 U相上升:       {get_bit(i_data, 0, 5)}')
    print(f'I0.6 U相下降:       {get_bit(i_data, 0, 6)}')
    print(f'I1.3 高压分闸:      {get_bit(i_data, 1, 3)}')
    print(f'I1.4 高压合闸:      {get_bit(i_data, 1, 4)}')
    print(f'I2.0 灵敏度增加:    {get_bit(i_data, 2, 0)}')
    print(f'I3.0 消音:          {get_bit(i_data, 3, 0)}')
    print(f'I3.6 变频器故障:    {get_bit(i_data, 3, 6)}')
    print(f'I4.2 系统运行标志:  {get_bit(i_data, 4, 2)}')

    print('\n=== 2. 输出位 (Outputs %Q0.0 - %Q4.1) ===')
    # 读取 5 个字节 (Byte 0-4)
    q_data = client.read_area(Areas.PA, 0, 0, 5)
    
    print(f'Q0.1 输出控制1:     {get_bit(q_data, 0, 1)}')
    print(f'Q0.5 自动模式反馈:  {get_bit(q_data, 0, 5)}')
    print(f'Q1.1 综合报警输出:  {get_bit(q_data, 1, 1)}')
    print(f'Q2.2 紧急停止输出:  {get_bit(q_data, 2, 2)}')
    print(f'Q3.5 称重完成输出:  {get_bit(q_data, 3, 5)}')

    print('\n=== 3. 模拟量输入 (%IW64 - %IW86) ===')
    # 读取 24 个字节 (Offset 64 start)
    iw_data = client.read_area(Areas.PE, 0, 64, 24)
    
    print(f'IW64 A相弧流:       {get_word(iw_data, 0)}')
    print(f'IW66 B相弧流:       {get_word(iw_data, 2)}')
    print(f'IW68 C相弧流:       {get_word(iw_data, 4)}')
    print(f'IW70 弧流给定:      {get_word(iw_data, 6)}')
    print(f'IW72 A相弧压:       {get_word(iw_data, 8)}')
    print(f'IW82 U相电机电流:   {get_word(iw_data, 18)}')

    print('\n=== 4. 模拟量输出 (%QW128 - %QW146) ===')
    # 读取 20 个字节 (Offset 128 start)
    qw_data = client.read_area(Areas.PA, 0, 128, 20)
    
    print(f'QW128 第一路电机:   {get_word(qw_data, 0)}')
    print(f'QW130 第二路电机:   {get_word(qw_data, 2)}')
    print(f'QW144 第三路电机:   {get_word(qw_data, 16)}')

except Exception as e:
    print(f'Error: {e}')
"

