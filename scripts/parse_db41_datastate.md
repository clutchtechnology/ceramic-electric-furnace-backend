cd D:\furnace-backend
venv\Scripts\python -c "
import struct
import sys
sys.path.insert(0, '.')
from app.plc.plc_manager import get_plc_manager

plc = get_plc_manager()
data, err = plc.read_db(41, 0, 28)

if data:
    data = bytes(data)
    print('=== DB41 DataState (28 bytes) ===')
    print()
    
    devices = [
        (0, 'LENTH1', 'Infrared 1'),
        (4, 'LENTH2', 'Infrared 2'),
        (8, 'LENTH3', 'Infrared 3'),
        (12, 'WATER_PRESS_1', 'Pressure 1'),
        (16, 'WATER_PRESS_2', 'Pressure 2'),
        (20, 'WATER_FLOW_1', 'Flow 1'),
        (24, 'WATER_FLOW_2', 'Flow 2'),
    ]
    
    print('--- Data State (Error + Status, 4 bytes each) ---')
    for offset, name, desc in devices:
        if offset + 4 <= len(data):
            error_byte = data[offset]
            error_bit = bool(error_byte & 0x01)
            status_word = struct.unpack('>H', data[offset+2:offset+4])[0]
            print(f'  [{offset:2d}-{offset+3}] {name:15s}: Error={error_bit}, Status={status_word} ({desc})')
    
    print()
    print('--- Raw hex dump ---')
    for i in range(0, 28, 16):
        hex_str = data[i:min(i+16, 28)].hex().upper()
        hex_fmt = ' '.join([hex_str[j:j+2] for j in range(0, len(hex_str), 2)])
        print(f'  {i:3d}: {hex_fmt}')
else:
    print(f'Read failed: {err}')
"