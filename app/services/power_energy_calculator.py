# ============================================================
# 文件说明: power_energy_calculator.py - 三相功率和能耗计算服务
# ============================================================
# 功能:
#   1. 实时计算三相功率 (P = U × I)
#   2. 基于时间戳的能耗累计计算 (梯形积分法)
#   3. 自适应 DB1 轮询间隔变化 (0.2s/5s)
#   4. 按批次重置累计能耗
# ============================================================
# 【数据库写入说明 - 功率和能耗数据】
# ============================================================
# 1: 实时功率 (与弧流弧压一起批量写入)
#    - 轮询间隔: 0.2秒(冶炼中) / 5秒(空闲)
#    - 批量写入: 20次轮询后写入 (4秒)
#    - 数据点: power_U/V/W (kW), power_total (kW)
# ============================================================
# 2: 累计能耗 (定时计算写入)
#    - 计算间隔: 每15秒计算一次
#    - 写入方式: 计算完成后立即写入
#    - 数据点: energy_U/V/W_total (kWh), energy_total (kWh)
# ============================================================
# 计算方法:
#   - 梯形积分法: E = Σ[(P1 + P2) / 2 × Δt]
#   - 比简单平均更精确，适应轮询间隔变化
# ============================================================

import threading
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from collections import deque
from dataclasses import dataclass


@dataclass
class PowerDataPoint:
    """单个功率数据点"""
    power_U: float          # U相功率 (kW)
    power_V: float          # V相功率 (kW)
    power_W: float          # W相功率 (kW)
    power_total: float      # 总功率 (kW)
    timestamp: datetime     # 时间戳


class PowerEnergyCalculator:
    """三相功率和能耗计算器 - 单例模式
    
    特点:
    1. 时间戳精确计算：记录每个数据点的时间戳
    2. 梯形积分法：E = Σ[(P1 + P2) / 2 × Δt]
    3. 自适应轮询间隔：自动适应 0.2s/5s 切换
    4. 定时计算：每15秒计算一次能耗增量
    """
    
    _instance: Optional['PowerEnergyCalculator'] = None
    _lock = threading.Lock()
    
    # 队列大小: 100个点 (足够覆盖15秒的数据)
    # 0.2s × 75 = 15s (高速)
    # 5s × 3 = 15s (低速)
    QUEUE_SIZE = 100
    
    # 计算间隔: 15秒
    CALC_INTERVAL_SEC = 15
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._data_lock = threading.Lock()
        
        # ============================================================
        # 功率数据队列 (带时间戳)
        # ============================================================
        self._power_queue: deque = deque(maxlen=self.QUEUE_SIZE)
        
        # ============================================================
        # 批次信息
        # ============================================================
        self._current_batch_code: Optional[str] = None
        
        # ============================================================
        # 上次计算时间
        # ============================================================
        self._last_calc_time: Optional[datetime] = None
        
        print("✅ 功率能耗计算器已初始化 (梯形积分法)")
    
    # ============================================================
    # 1: 批次管理模块
    # ============================================================
    def reset_for_new_batch(self, batch_code: str):
        """重置累计能耗 (新批次开始时调用)
        
        每次计算时从数据库查询最新值，无需预先恢复
        """
        with self._data_lock:
            # 清空队列和计时器
            self._power_queue.clear()
            self._last_calc_time = None
            self._current_batch_code = batch_code
            print(f"🆕 功率能耗计算器已重置 (批次: {batch_code})")
    
    def _get_latest_from_database(self, batch_code: str) -> Dict[str, float]:
        """从 InfluxDB 查询该批次的最新能耗累计值
        
        Returns:
            {
                'energy_total': float,
            }
        """
        try:
            from app.core.influxdb import get_influxdb_client
            from config import get_settings
            
            settings = get_settings()
            influx = get_influxdb_client()
            
            query = f'''
                from(bucket: "{settings.influx_bucket}")
                    |> range(start: -7d)
                    |> filter(fn: (r) => r["_measurement"] == "sensor_data")
                    |> filter(fn: (r) => r["batch_code"] == "{batch_code}")
                    |> filter(fn: (r) => r["module_type"] == "energy_consumption")
                    |> filter(fn: (r) => r["_field"] == "energy_total")
                    |> last()
            '''
            
            result = influx.query_api().query(query)
            
            energy_total = 0.0
            
            for table in result:
                for record in table.records:
                    value = record.get_value()
                    energy_total = float(value) if value else 0.0
                    break
            
            return {'energy_total': energy_total}
            
        except Exception as e:
            print(f"⚠️ 从数据库恢复能耗累计失败: {e}")
            return {'energy_total': 0.0}
    
    # ============================================================
    # 2: 功率计算模块
    # ============================================================
    def calculate_power(
        self,
        arc_current_U: float,
        arc_voltage_U: float,
        arc_current_V: float,
        arc_voltage_V: float,
        arc_current_W: float,
        arc_voltage_W: float,
    ) -> Dict[str, Any]:
        """计算总功率并添加到队列
        
        Args:
            arc_current_*: 弧流 (A)
            arc_voltage_*: 弧压 (V)
            
        Returns:
            {
                'power_total': float,       # 总功率 (kW)
                'should_calc_energy': bool, # 是否需要计算能耗
            }
        """
        with self._data_lock:
            # 1. 计算三相总功率 (kW)
            # P_total = (U_U × I_U + U_V × I_V + U_W × I_W) / 1000
            power_U = (arc_current_U * arc_voltage_U) / 1000
            power_V = (arc_current_V * arc_voltage_V) / 1000
            power_W = (arc_current_W * arc_voltage_W) / 1000
            power_total = power_U + power_V + power_W
            
            # 2. 创建数据点（只存储总功率）
            now = datetime.now(timezone.utc)
            point = PowerDataPoint(
                power_U=power_U,  # 内部保留用于计算
                power_V=power_V,  # 内部保留用于计算
                power_W=power_W,  # 内部保留用于计算
                power_total=power_total,
                timestamp=now
            )
            
            # 3. 添加到队列
            self._power_queue.append(point)
            
            # 4. 检查是否需要计算能耗 (每15秒)
            should_calc = False
            if self._last_calc_time is None:
                # 首次计算：等待至少10个数据点
                if len(self._power_queue) >= 10:
                    should_calc = True
                    self._last_calc_time = now
            else:
                # 后续计算：检查时间间隔
                elapsed = (now - self._last_calc_time).total_seconds()
                if elapsed >= self.CALC_INTERVAL_SEC:
                    should_calc = True
            
            return {
                'power_total': power_total,
                'should_calc_energy': should_calc,
            }
    
    # ============================================================
    # 3: 能耗计算模块 (梯形积分法)
    # ============================================================
    def calculate_energy_increment(self) -> Dict[str, Any]:
        """使用梯形积分法计算总能耗增量
        
        梯形积分法:
        E = Σ[(P1 + P2) / 2 × Δt]
        
        优点:
        - 比简单平均更精确
        - 自动适应轮询间隔变化
        - 考虑功率变化趋势
        
        Returns:
            {
                'energy_total_delta': float,  # 总能耗增量 (kWh)
                'energy_total': float,        # 总累计能耗 (kWh)
                'calc_duration': float,       # 计算时长 (秒)
                'data_points': int,           # 使用的数据点数
            }
        """
        with self._data_lock:
            # 更新计算时间
            now = datetime.now(timezone.utc)
            calc_duration = (now - self._last_calc_time).total_seconds() if self._last_calc_time else 0
            self._last_calc_time = now
            
            # 检查数据点数量
            if len(self._power_queue) < 2:
                latest = self._get_latest_from_database(self._current_batch_code) if self._current_batch_code else {}
                return {
                    'energy_total_delta': 0.0,
                    'energy_total': latest.get('energy_total', 0.0),
                    'calc_duration': calc_duration,
                    'data_points': len(self._power_queue),
                    'message': '数据点不足'
                }
            
            # ========================================
            # 梯形积分法计算总能耗
            # ========================================
            data_list = list(self._power_queue)
            
            energy_total_delta = 0.0
            
            for i in range(len(data_list) - 1):
                p1 = data_list[i]
                p2 = data_list[i + 1]
                
                # 时间差 (小时)
                dt_hours = (p2.timestamp - p1.timestamp).total_seconds() / 3600
                
                # 梯形积分: E = (P1 + P2) / 2 × Δt
                energy_total_delta += (p1.power_total + p2.power_total) / 2 * dt_hours
            
            # ========================================
            # 从数据库查询最新累计值
            # ========================================
            latest = self._get_latest_from_database(self._current_batch_code) if self._current_batch_code else {}
            
            # 累加
            new_energy_total = latest.get('energy_total', 0.0) + energy_total_delta
            
            # ========================================
            # 返回结果（不立即写入数据库，而是返回给调用者批量写入）
            # ========================================
            result = {
                'energy_total_delta': energy_total_delta,
                'energy_total': new_energy_total,
                'calc_duration': calc_duration,
                'data_points': len(data_list),
            }
            
            # 打印日志
            print(f"⚡ 能耗计算: 本次+{energy_total_delta:.4f}kWh, "
                  f"累计={new_energy_total:.2f}kWh, "
                  f"数据点={len(data_list)}, 时长={calc_duration:.1f}s")
            
            return result
    
    # ============================================================
    # 4: 数据获取模块
    # ============================================================
    def get_realtime_data(self) -> Dict[str, Any]:
        """获取实时数据 (供API调用)"""
        with self._data_lock:
            # 最新功率
            latest_power = self._power_queue[-1] if self._power_queue else None
            
            # 从数据库查询最新累计值
            latest_energy = self._get_latest_from_database(self._current_batch_code) if self._current_batch_code else {}
            
            return {
                'power_total': latest_power.power_total if latest_power else 0.0,
                'energy_total': latest_energy.get('energy_total', 0.0),
                'timestamp': latest_power.timestamp.isoformat() if latest_power else None,
                'batch_code': self._current_batch_code,
                'queue_size': len(self._power_queue),
            }


# ============================================================
# 全局单例获取函数
# ============================================================

_power_energy_calculator: Optional[PowerEnergyCalculator] = None

def get_power_energy_calculator() -> PowerEnergyCalculator:
    """获取功率能耗计算器单例"""
    global _power_energy_calculator
    if _power_energy_calculator is None:
        _power_energy_calculator = PowerEnergyCalculator()
    return _power_energy_calculator

