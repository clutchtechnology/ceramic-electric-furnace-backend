# 工具模块

from .converter_length import (
    LengthConverter,
    get_length_converter,
    convert_electrode_depth,
    convert_all_electrode_depths
)

from .converter_furnace import FurnaceConverter

from .operation_modbus_weight_reader import (
    read_hopper_weight,
    get_net_weight,
    parse_response_hex,
    mock_read_weight,
    build_read_request,
    parse_weight_response
)

from .converter_flow import (
    FlowConverter,
    FlowData,
    get_flow_converter,
    convert_flow,
    convert_flow_with_validation,
    convert_all_flows
)

from .converter_pressure import (
    PressureConverter,
    PressureData,
    get_pressure_converter,
    convert_pressure,
    convert_pressure_with_validation,
    convert_all_pressures
)

from .operation_button import (
    ValveConverter,
    ValveAction,
    ValveState,
    parse_valve_status,
    parse_all_valves,
    create_open_command,
    create_close_command,
    create_stop_command,
    create_all_stop_command
)

# DB1 弧流弧压转换器
from .converter_elec_db1 import (
    ArcPhaseData,
    ArcData,
    ArcDataConverter,
    get_arc_converter,
    convert_arc_current,
    convert_arc_voltage,
    convert_arc_phase,
    convert_db1_arc_data,
    convert_to_api_format,
    convert_to_influx_fields,
)

__all__ = [
    # 红外测距转换器
    'LengthConverter',
    'get_length_converter',
    'convert_electrode_depth',
    'convert_all_electrode_depths',
    # 电炉数据转换器
    'FurnaceConverter',
    # 料仓净重 Modbus 读取
    'read_hopper_weight',
    'get_net_weight',
    'parse_response_hex',
    'mock_read_weight',
    'build_read_request',
    'parse_weight_response',
    # 流量计转换器
    'FlowConverter',
    'FlowData',
    'get_flow_converter',
    'convert_flow',
    'convert_flow_with_validation',
    'convert_all_flows',
    # 压力计转换器
    'PressureConverter',
    'PressureData',
    'get_pressure_converter',
    'convert_pressure',
    'convert_pressure_with_validation',
    'convert_all_pressures',
    # 蝶阀控制转换器
    'ValveConverter',
    'ValveAction',
    'ValveState',
    'parse_valve_status',
    'parse_all_valves',
    'create_open_command',
    'create_close_command',
    'create_stop_command',
    'create_all_stop_command',
    # DB1 弧流弧压转换器
    'ArcPhaseData',
    'ArcData',
    'ArcDataConverter',
    'get_arc_converter',
    'convert_arc_current',
    'convert_arc_voltage',
    'convert_arc_phase',
    'convert_db1_arc_data',
    'convert_to_api_format',
    'convert_to_influx_fields',
]
