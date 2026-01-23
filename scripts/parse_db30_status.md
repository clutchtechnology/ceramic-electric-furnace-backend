docker exec -it furnace-backend python -c "
import struct
from app.plc.plc_manager import get_plc_manager

plc = get_plc_manager()
success, data, err = plc.read_db(30, 0, 32)

if success:
    data = bytes(data)
    devices = [
        (0, 'MB_COMM', '通信初始化状态'),
        (4, 'MB_MASTER_WRITE_1', '蝶阀控制写入状态'),
        (8, 'MB_MASTER_LENTH_1', '1号测距通信状态'),
        (12, 'MB_MASTER_LENTH_2', '2号测距通信状态'),
        (16, 'MB_MASTER_LENTH_3', '3号测距通信状态'),
        (20, 'MB_MASTER_WATER_1', '1号流量计通信状态'),
        (24, 'MB_MASTER_WATER_2', '2号流量计通信状态'),
        (28, 'MB_MASTER_PRESS_1', '1号压力计通信状态'),
    ]
    
    print('=== DB30 Modbus通信状态 ===')
    print('Raw Bytes:', list(data))
    print()
    
    for offset, plc_name, desc in devices:
        status_byte = data[offset]
        data_ptr = data[offset + 1]
        ndr = bool(status_byte & 0x80)
        error = bool(status_byte & 0x40)
        busy = bool(status_byte & 0x01)
        
        if error:
            status_str = '❌ 错误'
        elif ndr:
            status_str = '✅ 新数据就绪'
        elif busy:
            status_str = '⏳ 忙碌中'
        else:
            status_str = '⚪ 空闲'
        
        print(f'[Offset {offset:2d}] {plc_name:25s} ({desc})')
        print(f'  STATUS: {status_str} (Raw: 0x{status_byte:02X}) | Formula: NDR={ndr}, ERR={error}, BUSY={busy}')
        print(f'  Data_Ptr: {data_ptr}')
        print()
else:
    print(f'❌ 读取失败: {err}')
"
