cd D:\furnace-backend
venv\Scripts\python -c "
import struct
import sys
sys.path.insert(0, '.')
from app.plc.plc_manager import get_plc_manager

plc = get_plc_manager()
data, err = plc.read_db(32, 0, 21)

if data:
    data = bytes(data)
    print('=== DB32 MODBUS_DATA_VALUE (21 bytes) ===')
    print()
    
    # Parse known fields
    lenth1 = struct.unpack('>I', data[0:4])[0]
    lenth2 = struct.unpack('>I', data[4:8])[0]
    lenth3 = struct.unpack('>I', data[8:12])[0]
    water_press_1 = struct.unpack('>h', data[12:14])[0]
    water_press_2 = struct.unpack('>h', data[14:16])[0]
    water_flow_1 = struct.unpack('>h', data[16:18])[0]
    water_flow_2 = struct.unpack('>h', data[18:20])[0]
    valve_status = data[20]
    
    print('--- Infrared Distance (UDInt, mm) ---')
    print(f'  LENTH1 (offset 0-3):  {lenth1} mm')
    print(f'  LENTH2 (offset 4-7):  {lenth2} mm')
    print(f'  LENTH3 (offset 8-11): {lenth3} mm')
    print()
    print('--- Water Pressure (Int) ---')
    print(f'  WATER_PRESS_1 (offset 12-13): {water_press_1}')
    print(f'  WATER_PRESS_2 (offset 14-15): {water_press_2}')
    print()
    print('--- Water Flow (Int) ---')
    print(f'  WATER_FLOW_1 (offset 16-17): {water_flow_1}')
    print(f'  WATER_FLOW_2 (offset 18-19): {water_flow_2}')
    print()
    print('--- Valve Status (Byte) ---')
    print(f'  Valve Status (offset 20): {valve_status} (bin: {bin(valve_status)})')
    print()
    print('--- Raw hex dump ---')
    print(f'  {data.hex().upper()}')
else:
    print(f'Read failed: {err}')
"