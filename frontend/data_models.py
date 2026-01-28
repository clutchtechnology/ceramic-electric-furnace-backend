"""
前端数据模型定义

说明：
- 这些数据模型用于前端 PyQt6 GUI
- 与 app/models/ 中的 FastAPI 模型不同
- 使用 dataclass 提供类型提示和默认值
- 用于缓存、信号传递、UI 显示

区别：
- app/models/: FastAPI Pydantic 模型（用于 API 验证）
- frontend/data_models.py: 前端数据结构（用于 GUI 显示）
"""
from dataclasses import dataclass, field
from typing import Dict, Optional
from datetime import datetime


@dataclass
class ElectrodeData:
    """单个电极数据"""
    phase: str  # 'U', 'V', 'W'
    arc_current: float = 0.0  # 弧流 (A)
    arc_voltage: float = 0.0  # 弧压 (V)
    setpoint: float = 0.0  # 设定值 (A)
    depth: float = 0.0  # 深度 (mm)
    
    # 报警状态
    current_alarm: bool = False  # 电流报警
    depth_alarm: bool = False  # 深度报警
    
    def __repr__(self):
        return f"Electrode({self.phase}: {self.arc_current}A, {self.arc_voltage}V, {self.depth}mm)"


@dataclass
class ArcData:
    """弧流弧压数据（3个电极）"""
    electrodes: Dict[str, ElectrodeData] = field(default_factory=dict)
    manual_deadzone_percent: float = 0.0  # 手动死区百分比
    timestamp: float = 0.0
    
    def __post_init__(self):
        """初始化 3 个电极"""
        if not self.electrodes:
            self.electrodes = {
                'U': ElectrodeData(phase='U'),
                'V': ElectrodeData(phase='V'),
                'W': ElectrodeData(phase='W')
            }
    
    def get_electrode(self, phase: str) -> ElectrodeData:
        """获取指定相的电极数据"""
        return self.electrodes.get(phase, ElectrodeData(phase=phase))


@dataclass
class CoolingWaterData:
    """冷却水数据"""
    inlet_temp: float = 0.0  # 进水温度 (°C)
    outlet_temp: float = 0.0  # 出水温度 (°C)
    flow_rate: float = 0.0  # 流量 (m³/h)
    pressure: float = 0.0  # 压力 (MPa)
    
    # 报警状态
    temp_alarm: bool = False
    flow_alarm: bool = False
    pressure_alarm: bool = False


@dataclass
class HopperData:
    """料仓数据"""
    weight_1: float = 0.0  # 1号料仓重量 (kg)
    weight_2: float = 0.0  # 2号料仓重量 (kg)
    weight_3: float = 0.0  # 3号料仓重量 (kg)
    
    # 报警状态
    low_level_alarm: bool = False


@dataclass
class ValveStatus:
    """阀门状态"""
    valve_id: str  # 阀门编号
    is_open: bool = False  # 是否打开
    is_closed: bool = False  # 是否关闭
    is_stopped: bool = True  # 是否停止
    openness_percent: float = 0.0  # 开度百分比
    
    def get_status_text(self) -> str:
        """获取状态文本"""
        if self.is_open:
            return "开启中"
        elif self.is_closed:
            return "关闭中"
        elif self.is_stopped:
            return "停止"
        return "未知"


@dataclass
class DustCollectorData:
    """除尘器数据"""
    fan_running: bool = False  # 风机运行
    valve_1: ValveStatus = field(default_factory=lambda: ValveStatus(valve_id='1'))
    valve_2: ValveStatus = field(default_factory=lambda: ValveStatus(valve_id='2'))
    valve_3: ValveStatus = field(default_factory=lambda: ValveStatus(valve_id='3'))
    valve_4: ValveStatus = field(default_factory=lambda: ValveStatus(valve_id='4'))


@dataclass
class SensorData:
    """传感器数据（汇总）"""
    cooling_water: CoolingWaterData = field(default_factory=CoolingWaterData)
    hopper: HopperData = field(default_factory=HopperData)
    dust_collector: DustCollectorData = field(default_factory=DustCollectorData)
    timestamp: float = 0.0


@dataclass
class BatchStatus:
    """批次状态"""
    is_smelting: bool = False  # 是否正在冶炼
    batch_code: str = ""  # 批次号
    start_time: Optional[datetime] = None  # 开始时间
    elapsed_seconds: int = 0  # 已用时间（秒）
    
    def get_elapsed_time_text(self) -> str:
        """获取已用时间文本（HH:MM:SS）"""
        hours = self.elapsed_seconds // 3600
        minutes = (self.elapsed_seconds % 3600) // 60
        seconds = self.elapsed_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


@dataclass
class AlarmRecord:
    """报警记录"""
    alarm_id: str  # 报警ID
    alarm_type: str  # 报警类型
    alarm_message: str  # 报警信息
    alarm_level: str  # 报警级别（warning, error, critical）
    timestamp: datetime = field(default_factory=datetime.now)
    is_acknowledged: bool = False  # 是否已确认
    
    def get_level_color(self) -> str:
        """获取报警级别颜色"""
        colors = {
            'warning': '#FFA500',  # 橙色
            'error': '#FF4444',  # 红色
            'critical': '#FF0000'  # 深红色
        }
        return colors.get(self.alarm_level, '#FFFFFF')


@dataclass
class HistoryDataPoint:
    """历史数据点（用于图表）"""
    timestamp: datetime
    value: float
    label: str = ""  # 数据标签（如 "U相电流"）
    
    def get_timestamp_ms(self) -> int:
        """获取时间戳（毫秒）"""
        return int(self.timestamp.timestamp() * 1000)


# ========== 数据转换工具函数 ==========

def dict_to_arc_data(data: Dict) -> ArcData:
    """将字典转换为 ArcData 对象
    
    Args:
        data: 弧流数据字典
    
    Returns:
        ArcData 对象
    """
    arc_data = ArcData(
        manual_deadzone_percent=data.get('manual_deadzone_percent', 0.0),
        timestamp=data.get('timestamp', 0.0)
    )
    
    # 转换电极数据
    arc_current = data.get('arc_current', {})
    arc_voltage = data.get('arc_voltage', {})
    setpoints = data.get('setpoints', {})
    depths = data.get('electrode_depths', {})
    
    for phase in ['U', 'V', 'W']:
        arc_data.electrodes[phase] = ElectrodeData(
            phase=phase,
            arc_current=arc_current.get(phase, 0.0),
            arc_voltage=arc_voltage.get(phase, 0.0),
            setpoint=setpoints.get(phase, 0.0),
            depth=depths.get(phase, 0.0)
        )
    
    return arc_data


def dict_to_sensor_data(data: Dict) -> SensorData:
    """将字典转换为 SensorData 对象
    
    Args:
        data: 传感器数据字典
    
    Returns:
        SensorData 对象
    """
    sensor_data = SensorData(timestamp=data.get('timestamp', 0.0))
    
    # 冷却水数据
    cooling = data.get('cooling', {})
    sensor_data.cooling_water = CoolingWaterData(
        inlet_temp=cooling.get('inlet_temp', 0.0),
        outlet_temp=cooling.get('outlet_temp', 0.0),
        flow_rate=cooling.get('flow_rate', 0.0),
        pressure=cooling.get('pressure', 0.0)
    )
    
    # 料仓数据
    hopper = data.get('hopper', {})
    sensor_data.hopper = HopperData(
        weight_1=hopper.get('weight_1', 0.0),
        weight_2=hopper.get('weight_2', 0.0),
        weight_3=hopper.get('weight_3', 0.0)
    )
    
    # 除尘器数据
    dust = data.get('dust_collector', {})
    sensor_data.dust_collector = DustCollectorData(
        fan_running=dust.get('fan_running', False)
    )
    
    # 阀门状态
    valve_status = data.get('valve_status', {})
    valve_openness = data.get('valve_openness', {})
    
    for i in range(1, 5):
        valve_id = str(i)
        status = valve_status.get(valve_id, {})
        valve = ValveStatus(
            valve_id=valve_id,
            is_open=status.get('is_open', False),
            is_closed=status.get('is_closed', False),
            is_stopped=status.get('is_stopped', True),
            openness_percent=valve_openness.get(valve_id, 0.0)
        )
        setattr(sensor_data.dust_collector, f'valve_{valve_id}', valve)
    
    return sensor_data


def dict_to_batch_status(data: Dict) -> BatchStatus:
    """将字典转换为 BatchStatus 对象
    
    Args:
        data: 批次状态字典
    
    Returns:
        BatchStatus 对象
    """
    start_time = None
    if data.get('start_time'):
        start_time = datetime.fromtimestamp(data['start_time'])
    
    return BatchStatus(
        is_smelting=data.get('is_smelting', False),
        batch_code=data.get('batch_code', ''),
        start_time=start_time,
        elapsed_seconds=data.get('elapsed_seconds', 0)
    )

