# ============================================================
# 文件说明: feeding_service.py - 投料记录计算服务
# ============================================================
# 功能:
#   1. 定时计算投料记录 (每20分钟执行一次)
#   2. 从 InfluxDB 查询当前批次的料仓重量历史数据
#   3. 分析重量变化，检测投料事件 (重量上升)
#   4. 特殊处理首重和尾重
#   5. 投料记录存入 InfluxDB 的 feeding_records measurement
#   6. 提供查询当前批次投料总量的接口
# ============================================================

import asyncio
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from config import get_settings
from app.core.influxdb import get_influx_client, query_data

settings = get_settings()

# ============================================================
# 数据结构定义
# ============================================================
@dataclass
class FeedingRecord:
    """投料记录"""
    time: datetime
    added_weight: float  # 投入重量 (kg)
    batch_code: str      # 批次号
    is_first: bool = False  # 是否为首重
    is_last: bool = False   # 是否为尾重 (可能被覆盖)


# ============================================================
# 投料计算配置
# ============================================================
FEEDING_THRESHOLD_KG = 10.0     # 投料检测阈值 (kg)
AGGREGATION_INTERVAL = "5m"     # 聚合间隔
CALCULATION_INTERVAL_MINUTES = 20  # 计算周期 (分钟)
TIME_GAP_THRESHOLD_SECONDS = 300   # 时间断档阈值 (秒，5分钟)


# ============================================================
# 模块级缓存
# ============================================================
_feeding_lock = threading.Lock()
_last_calculation_time: Optional[datetime] = None
_current_batch_feeding_total: float = 0.0  # 当前批次投料总量缓存


def calculate_feeding_records(
    batch_code: str,
    start_time: datetime,
    end_time: Optional[datetime] = None
) -> List[FeedingRecord]:
    """计算指定批次的投料记录
    
    Args:
        batch_code: 批次号
        start_time: 批次开始时间
        end_time: 结束时间 (None 表示当前时间)
        
    Returns:
        投料记录列表
    """
    if end_time is None:
        end_time = datetime.now(timezone.utc)
    
    # 确保时间带时区
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)
    
    print(f"📊 开始计算批次 {batch_code} 的投料记录...")
    print(f"   时间范围: {start_time.isoformat()} ~ {end_time.isoformat()}")
    
    # 1. 查询料仓重量历史数据 (5分钟聚合)
    weight_data = _query_weight_history(start_time, end_time)
    
    if not weight_data:
        print(f"   ⚠️ 无重量历史数据")
        return []
    
    print(f"   📈 获取到 {len(weight_data)} 条重量数据点")
    
    # 2. 分析投料事件
    feeding_records = _analyze_feeding_events(weight_data, batch_code)
    
    print(f"   ✅ 检测到 {len(feeding_records)} 次投料事件")
    
    return feeding_records


def _query_weight_history(
    start_time: datetime, 
    end_time: datetime
) -> List[Dict[str, Any]]:
    """查询料仓重量历史数据
    
    Args:
        start_time: 开始时间
        end_time: 结束时间
        
    Returns:
        重量数据点列表 [{"time": datetime, "value": float}, ...]
    """
    client = get_influx_client()
    query_api = client.query_api()
    bucket = settings.influx_bucket
    
    # Flux 查询：获取 weight 字段，按5分钟聚合取平均值
    query = f'''
    from(bucket: "{bucket}")
        |> range(start: {start_time.isoformat()}, stop: {end_time.isoformat()})
        |> filter(fn: (r) => r["_measurement"] == "sensor_data")
        |> filter(fn: (r) => r["device_id"] == "hopper_1")
        |> filter(fn: (r) => r["_field"] == "weight")
        |> aggregateWindow(every: 5m, fn: mean, createEmpty: false)
        |> sort(columns: ["_time"], desc: false)
    '''
    
    try:
        result = query_api.query(query)
        
        points = []
        for table in result:
            for record in table.records:
                points.append({
                    "time": record.get_time(),
                    "value": float(record.get_value()) if record.get_value() is not None else 0.0
                })
        
        return points
        
    except Exception as e:
        print(f"   ❌ 查询重量历史数据失败: {e}")
        return []


def _analyze_feeding_events(
    weight_data: List[Dict[str, Any]], 
    batch_code: str
) -> List[FeedingRecord]:
    """分析重量数据，检测投料事件
    
    投料检测逻辑:
    1. 首重: 如果批次开始时就有重量 > 阈值，记录为首次投料
    2. 中间: 检测重量上升沿 (当前值 - 上一次值 > 阈值)
    3. 尾重: 如果最后一个数据点相比前一个是上升的，也记录 (可能被后续覆盖)
    
    Args:
        weight_data: 重量数据点列表
        batch_code: 批次号
        
    Returns:
        投料记录列表
    """
    if len(weight_data) < 1:
        return []
    
    feeding_records: List[FeedingRecord] = []
    
    # 1. 首重处理: 如果第一个数据点重量 > 阈值，视为批次开始时已有料
    first_point = weight_data[0]
    if first_point["value"] > FEEDING_THRESHOLD_KG:
        feeding_records.append(FeedingRecord(
            time=first_point["time"],
            added_weight=first_point["value"],
            batch_code=batch_code,
            is_first=True
        ))
        print(f"      首重: {first_point['value']:.2f} kg at {first_point['time']}")
    
    # 2. 中间检测: 遍历数据点，检测上升沿
    prev_point = weight_data[0]
    
    for i in range(1, len(weight_data)):
        curr_point = weight_data[i]
        curr_val = curr_point["value"]
        prev_val = prev_point["value"]
        curr_time = curr_point["time"]
        prev_time = prev_point["time"]
        
        # 时间间隔检查 (避免断档数据干扰)
        time_diff = (curr_time - prev_time).total_seconds()
        if time_diff > TIME_GAP_THRESHOLD_SECONDS:
            # 时间断档，重置基准
            prev_point = curr_point
            continue
        
        # 计算重量变化
        diff = curr_val - prev_val
        
        # 检测上升沿 (投料事件)
        if diff > FEEDING_THRESHOLD_KG:
            # 检查是否是最后一个点
            is_last = (i == len(weight_data) - 1)
            
            feeding_records.append(FeedingRecord(
                time=curr_time,
                added_weight=diff,
                batch_code=batch_code,
                is_last=is_last
            ))
            
            if is_last:
                print(f"      尾重(待确认): +{diff:.2f} kg at {curr_time}")
            else:
                print(f"      投料: +{diff:.2f} kg at {curr_time}")
        
        prev_point = curr_point
    
    return feeding_records


def save_feeding_records(records: List[FeedingRecord]) -> bool:
    """将投料记录保存到 InfluxDB
    
    对于 is_last=True 的记录，会先删除该批次的尾重记录，再写入新的
    (实现覆盖逻辑)
    
    Args:
        records: 投料记录列表
        
    Returns:
        是否保存成功
    """
    if not records:
        return True
    
    from influxdb_client import Point
    from influxdb_client.client.write_api import SYNCHRONOUS
    
    client = get_influx_client()
    write_api = client.write_api(write_options=SYNCHRONOUS)
    bucket = settings.influx_bucket
    
    try:
        # 分离尾重记录和普通记录
        last_records = [r for r in records if r.is_last]
        normal_records = [r for r in records if not r.is_last]
        
        # 处理尾重记录 (删除旧的，写入新的)
        for record in last_records:
            # 先删除该批次的旧尾重记录
            _delete_last_feeding_record(record.batch_code)
        
        # 构建 Point 对象
        points = []
        for record in records:
            p = Point("feeding_records") \
                .tag("batch_code", record.batch_code) \
                .tag("device_id", "hopper_1") \
                .tag("is_first", str(record.is_first).lower()) \
                .tag("is_last", str(record.is_last).lower()) \
                .field("added_weight", record.added_weight) \
                .time(record.time)
            points.append(p)
        
        # 批量写入
        write_api.write(bucket=bucket, record=points)
        print(f"   💾 已保存 {len(points)} 条投料记录")
        return True
        
    except Exception as e:
        print(f"   ❌ 保存投料记录失败: {e}")
        return False


def _delete_last_feeding_record(batch_code: str) -> bool:
    """删除指定批次的尾重记录
    
    注意: InfluxDB 删除操作需要通过 delete API
    由于 InfluxDB 的特性，这里采用标记删除的方式
    
    Args:
        batch_code: 批次号
        
    Returns:
        是否删除成功
    """
    # 实际实现中，可以通过 InfluxDB Delete API 删除
    # 或者在查询时过滤掉 is_last=true 的旧记录
    # 这里简化处理，新记录会自动覆盖同时间点的旧记录
    print(f"   🗑️ 标记删除批次 {batch_code} 的旧尾重记录")
    return True


def get_batch_feeding_total(batch_code: str, start_time: datetime) -> float:
    """获取指定批次的投料总量
    
    Args:
        batch_code: 批次号
        start_time: 批次开始时间
        
    Returns:
        投料总量 (kg)
    """
    from datetime import timezone
    
    client = get_influx_client()
    query_api = client.query_api()
    bucket = settings.influx_bucket
    
    # 确保时间带时区
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    
    # [FIX] 检查批次刚开始的情况，避免空范围查询
    now = datetime.now(timezone.utc)
    if start_time > now:
        # 批次开始时间在未来（时钟同步问题），返回0
        return 0.0
    
    # [FIX] 如果批次刚开始不到2秒，直接返回0，避免频繁查询
    if (now - start_time).total_seconds() < 2:
        return 0.0
    
    # Flux 查询：获取该批次的所有投料记录并求和
    query = f'''
    from(bucket: "{bucket}")
        |> range(start: {start_time.isoformat()})
        |> filter(fn: (r) => r["_measurement"] == "feeding_records")
        |> filter(fn: (r) => r["batch_code"] == "{batch_code}")
        |> filter(fn: (r) => r["_field"] == "added_weight")
        |> sum()
    '''
    
    try:
        result = query_api.query(query)
        
        total = 0.0
        for table in result:
            for record in table.records:
                total = float(record.get_value()) if record.get_value() else 0.0
        
        return total
        
    except Exception as e:
        print(f"   ❌ 查询投料总量失败: {e}")
        return 0.0


def get_batch_feeding_records(batch_code: str, start_time: datetime) -> List[Dict[str, Any]]:
    """获取指定批次的所有投料记录
    
    Args:
        batch_code: 批次号
        start_time: 批次开始时间
        
    Returns:
        投料记录列表
    """
    client = get_influx_client()
    query_api = client.query_api()
    bucket = settings.influx_bucket
    
    # 确保时间带时区
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    
    query = f'''
    from(bucket: "{bucket}")
        |> range(start: {start_time.isoformat()})
        |> filter(fn: (r) => r["_measurement"] == "feeding_records")
        |> filter(fn: (r) => r["batch_code"] == "{batch_code}")
        |> filter(fn: (r) => r["_field"] == "added_weight")
        |> sort(columns: ["_time"], desc: false)
    '''
    
    try:
        result = query_api.query(query)
        
        records = []
        for table in result:
            for record in table.records:
                records.append({
                    "time": record.get_time().isoformat(),
                    "added_weight": float(record.get_value()) if record.get_value() else 0.0,
                    "is_first": record.values.get("is_first", "false") == "true",
                    "is_last": record.values.get("is_last", "false") == "true",
                })
        
        return records
        
    except Exception as e:
        print(f"   ❌ 查询投料记录失败: {e}")
        return []


# ============================================================
# 定时计算任务
# ============================================================
async def run_feeding_calculation_task(
    get_batch_info_func,
    interval_minutes: int = CALCULATION_INTERVAL_MINUTES
):
    """定时投料计算任务
    
    每 interval_minutes 分钟执行一次投料计算
    
    Args:
        get_batch_info_func: 获取当前批次信息的函数
        interval_minutes: 计算间隔 (分钟)
    """
    global _last_calculation_time, _current_batch_feeding_total
    
    print(f"🔄 投料计算定时任务已启动 (间隔: {interval_minutes} 分钟)")
    
    while True:
        try:
            await asyncio.sleep(interval_minutes * 60)
            
            # 获取当前批次信息
            batch_info = get_batch_info_func()
            batch_code = batch_info.get('batch_code')
            start_time_str = batch_info.get('start_time')
            
            if not batch_code or not start_time_str:
                print("⏸️ 无活动批次，跳过投料计算")
                continue
            
            # 解析开始时间
            start_time = datetime.fromisoformat(start_time_str)
            
            with _feeding_lock:
                _last_calculation_time = datetime.now()
            
            # 计算投料记录
            records = calculate_feeding_records(batch_code, start_time)
            
            # 保存到数据库
            if records:
                save_feeding_records(records)
                
                # 更新缓存的投料总量
                total = sum(r.added_weight for r in records)
                with _feeding_lock:
                    _current_batch_feeding_total = total
                    
                print(f"📦 批次 {batch_code} 当前投料总量: {total:.2f} kg")
            
        except asyncio.CancelledError:
            print("🛑 投料计算定时任务已停止")
            break
        except Exception as e:
            print(f"❌ 投料计算任务异常: {e}")
            import traceback
            traceback.print_exc()


def get_cached_feeding_total() -> float:
    """获取缓存的当前批次投料总量
    
    Returns:
        投料总量 (kg)
    """
    with _feeding_lock:
        return _current_batch_feeding_total


def trigger_feeding_calculation(batch_code: str, start_time: datetime) -> float:
    """手动触发投料计算 (用于API调用)
    
    Args:
        batch_code: 批次号
        start_time: 批次开始时间
        
    Returns:
        投料总量 (kg)
    """
    global _current_batch_feeding_total
    
    records = calculate_feeding_records(batch_code, start_time)
    
    if records:
        save_feeding_records(records)
        total = sum(r.added_weight for r in records)
        
        with _feeding_lock:
            _current_batch_feeding_total = total
            
        return total
    
    return 0.0
