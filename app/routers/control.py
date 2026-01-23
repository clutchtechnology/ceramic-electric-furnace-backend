# ============================================================
# 文件说明: control.py - 轮询控制路由
# ============================================================
# 功能:
#   1. 启动轮询服务 (接收批次号)
#   2. 停止轮询服务
#   3. 查询轮询状态
#   4. 查询/切换 Mock 模式
# ============================================================

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from config import get_settings, reload_settings
from app.services import polling_service

router = APIRouter()


class StartPollingRequest(BaseModel):
    """启动轮询请求"""
    batch_code: str  # 批次号 (格式: SM20260122001)


class StartPollingResponse(BaseModel):
    """启动轮询响应"""
    status: str
    message: str
    batch_code: str
    start_time: str
    mode: Optional[str] = None  # mock 或 plc


class StopPollingResponse(BaseModel):
    """停止轮询响应"""
    status: str
    message: str
    batch_code: Optional[str] = None
    start_time: Optional[str] = None
    stop_time: Optional[str] = None
    duration_seconds: Optional[float] = None


class PollingStatusResponse(BaseModel):
    """轮询状态响应"""
    is_running: bool
    batch_code: Optional[str] = None
    start_time: Optional[str] = None
    current_time: str
    duration_seconds: Optional[float] = None
    mode: Optional[str] = None  # mock 或 plc
    statistics: dict


class MockModeResponse(BaseModel):
    """Mock 模式响应"""
    mock_mode: bool
    message: str


class SetMockModeRequest(BaseModel):
    """设置 Mock 模式请求"""
    mock_mode: bool


@router.post("/start", response_model=StartPollingResponse, summary="开始冶炼 (切换DB1高速)")
async def start_polling(request: StartPollingRequest):
    """
    开始冶炼 - 切换 DB1 弧流弧压轮询到高速模式 (0.2s)
    
    - **batch_code**: 批次号，由前端生成 (格式: SM + YYYYMMDD + 序号)
    - **作用**: 
      1. 设置批次号
      2. 将 DB1 轮询从 5s 切换到 0.2s
      3. 启动投料计算任务
    - **注意**: 轮询服务已自动运行，此接口仅切换速度
    """
    try:
        # 1. 切换 DB1 到高速模式
        from app.services.polling_loops_v2 import switch_db1_speed
        switch_db1_speed(high_speed=True)
        
        # 2. 设置批次号和冶炼状态
        from app.services.polling_service import start_smelting
        result = start_smelting(request.batch_code)
        
        # 3. 启动投料计算任务
        from app.services.feeding_service import run_feeding_calculation_task, CALCULATION_INTERVAL_MINUTES
        from app.services.polling_service import get_batch_info
        
        # TODO: 需要在 polling_service 中维护 feeding_task
        print(f"📦 投料计算任务需要手动启动 (间隔: {CALCULATION_INTERVAL_MINUTES} 分钟)")
        
        return StartPollingResponse(
            status="success",
            message=f"冶炼已开始，DB1轮询切换到0.2s",
            batch_code=result['batch_code'],
            start_time=result['start_time'],
            mode="high_speed"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动冶炼失败: {str(e)}")


@router.post("/stop", response_model=StopPollingResponse, summary="停止冶炼 (切换DB1低速)")
async def stop_polling():
    """
    停止冶炼 - 将 DB1 弧流弧压轮询切换到低速模式 (5s)
    
    - **作用**:
      1. 停止冶炼状态
      2. 将 DB1 轮询从 0.2s 切换回 5s
      3. 停止投料计算任务
    - **注意**: 轮询服务不会停止，仅切换速度
    """
    try:
        # 1. 切换 DB1 到低速模式
        from app.services.polling_loops_v2 import switch_db1_speed
        switch_db1_speed(high_speed=False)
        
        # 2. 停止冶炼状态
        from app.services.polling_service import stop_smelting
        result = stop_smelting()
        
        # 计算运行时长
        duration = None
        if result.get("start_time") and result.get("end_time"):
            start = datetime.fromisoformat(result["start_time"])
            stop = datetime.fromisoformat(result["end_time"])
            duration = (stop - start).total_seconds()
        
        return StopPollingResponse(
            status="success",
            message="冶炼已停止，DB1轮询切换到5s",
            batch_code=result.get("batch_code"),
            start_time=result.get("start_time"),
            stop_time=result.get("end_time"),
            duration_seconds=duration
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"停止冶炼失败: {str(e)}")


@router.get("/status", response_model=PollingStatusResponse, summary="查询轮询状态")
async def get_polling_status():
    """
    查询当前轮询服务状态
    
    - **is_running**: 是否正在运行 (新架构下始终为 true)
    - **batch_code**: 当前批次号
    - **start_time**: 启动时间
    - **duration_seconds**: 已运行时长 (秒)
    - **mode**: DB1 轮询速度 (high_speed=0.2s, low_speed=5s)
    - **statistics**: 统计信息 (总轮询次数/成功次数/失败次数)
    """
    try:
        # 获取轮询循环状态
        from app.services.polling_loops_v2 import get_polling_loops_status
        loops_status = get_polling_loops_status()
        
        # 获取批次信息
        from app.services.polling_service import get_batch_info, get_polling_stats
        batch_info = get_batch_info()
        stats = get_polling_stats()
        
        current_time = datetime.now().isoformat()
        
        # 计算运行时长
        duration = batch_info.get('duration_seconds')
        
        # 判断模式
        mode = "high_speed" if loops_status['db1_interval'] == 0.2 else "low_speed"
        
        return PollingStatusResponse(
            is_running=loops_status['db1_running'],
            batch_code=batch_info.get('batch_code'),
            start_time=batch_info.get('start_time'),
            current_time=current_time,
            duration_seconds=duration,
            mode=mode,
            statistics=stats.get('stats', {})
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询状态失败: {str(e)}")


# ============================================================
# Mock 模式控制接口
# ============================================================

@router.get("/mock-mode", response_model=MockModeResponse, summary="查询 Mock 模式状态")
async def get_mock_mode():
    """
    查询当前 Mock 模式状态
    
    - **mock_mode=true**: 使用 Mock 数据 (开发/测试环境)
    - **mock_mode=false**: 使用真实 PLC 数据 (生产环境)
    """
    settings = get_settings()
    return MockModeResponse(
        mock_mode=settings.mock_mode,
        message=f"当前为 {'Mock' if settings.mock_mode else 'PLC'} 模式"
    )


@router.post("/mock-mode", response_model=MockModeResponse, summary="切换 Mock 模式")
async def set_mock_mode(request: SetMockModeRequest):
    """
    切换 Mock 模式
    
    ⚠️ **注意**: 切换模式需要先停止轮询服务，再重新启动
    
    - **mock_mode=true**: 切换到 Mock 模式 (开发/测试)
    - **mock_mode=false**: 切换到 PLC 模式 (生产)
    """
    # 检查轮询是否正在运行
    status = polling_service.get_polling_status()
    if status["is_running"]:
        raise HTTPException(
            status_code=400,
            detail="请先停止轮询服务再切换模式 (POST /api/control/stop)"
        )
    
    # 由于 pydantic_settings 不支持运行时修改配置
    # 需要通过环境变量或 .env 文件来切换
    # 这里提供一个临时的运行时切换方案
    
    import os
    os.environ["MOCK_MODE"] = str(request.mock_mode).lower()
    
    # 重新加载配置
    new_settings = reload_settings()
    
    return MockModeResponse(
        mock_mode=new_settings.mock_mode,
        message=f"已切换到 {'Mock' if new_settings.mock_mode else 'PLC'} 模式，下次启动轮询时生效"
    )
