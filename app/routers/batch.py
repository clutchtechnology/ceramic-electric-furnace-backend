# ============================================================
# 文件说明: batch.py - 批次管理API路由
# ============================================================
# 接口:
#   POST /api/batch/start   - 开始冶炼
#   POST /api/batch/pause   - 暂停冶炼
#   POST /api/batch/resume  - 恢复冶炼
#   POST /api/batch/stop    - 停止冶炼
#   GET  /api/batch/status  - 获取状态（断电恢复用）
# ============================================================

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from ..services.batch_service import get_batch_service


router = APIRouter(prefix="/api/batch", tags=["批次管理"])


# ============================================================
# 请求/响应模型
# ============================================================

class StartRequest(BaseModel):
    """开始冶炼请求"""
    batch_code: str = Field(..., description="批次编号，格式: YYMMFFDD (如 26010315)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "batch_code": "26010315"
            }
        }


class BatchResponse(BaseModel):
    """通用批次响应"""
    success: bool
    message: str
    batch_code: Optional[str] = None
    

class StatusResponse(BaseModel):
    """状态响应（用于断电恢复）"""
    state: str  # idle, running, paused, stopped
    is_smelting: bool  # 是否有活跃批次
    is_running: bool   # 是否正在写数据库
    batch_code: Optional[str]
    start_time: Optional[str]
    pause_time: Optional[str]
    elapsed_seconds: float
    total_pause_duration: float


# ============================================================
# API 路由
# ============================================================

@router.post("/start", response_model=BatchResponse, summary="开始冶炼")
async def start_smelting(request: StartRequest):
    """
    开始新的冶炼批次
    
    - 设置批次编号
    - 开始记录数据到数据库
    - 如果已有进行中的批次，返回错误
    """
    service = get_batch_service()
    result = service.start(request.batch_code)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return BatchResponse(
        success=True,
        message=result["message"],
        batch_code=result["batch_code"]
    )


@router.post("/pause", response_model=BatchResponse, summary="暂停冶炼")
async def pause_smelting():
    """
    暂停当前冶炼
    
    - 保留批次编号
    - 暂停写入数据库
    - 记录暂停时长
    """
    service = get_batch_service()
    result = service.pause()
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return BatchResponse(
        success=True,
        message=result["message"],
        batch_code=result.get("batch_code")
    )


@router.post("/resume", response_model=BatchResponse, summary="恢复冶炼")
async def resume_smelting():
    """
    恢复暂停的冶炼
    
    - 继续使用原批次编号
    - 恢复写入数据库
    - 累计暂停时长
    """
    service = get_batch_service()
    result = service.resume()
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return BatchResponse(
        success=True,
        message=result["message"],
        batch_code=result.get("batch_code")
    )


@router.post("/stop", response_model=BatchResponse, summary="停止冶炼")
async def stop_smelting():
    """
    停止当前冶炼
    
    - 结束批次
    - 清除批次编号
    - 返回冶炼摘要
    """
    service = get_batch_service()
    result = service.stop()
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return BatchResponse(
        success=True,
        message=result["message"],
        batch_code=None
    )


@router.get("/status", response_model=StatusResponse, summary="获取状态")
async def get_status():
    """
    获取当前冶炼状态
    
    **用途**:
    - 前端启动时检查是否有未完成的批次（断电恢复）
    - 前端定期同步状态
    
    **断电恢复流程**:
    1. 前端启动时调用此接口
    2. 如果 is_smelting=true 且 state=paused，说明有未完成批次
    3. 前端显示恢复对话框，用户选择恢复或放弃
    """
    service = get_batch_service()
    status = service.get_status()
    
    return StatusResponse(**status)


class LatestSequenceResponse(BaseModel):
    """最新批次序号响应"""
    success: bool
    furnace_number: str
    year: int
    month: int
    latest_sequence: int  # 最新序号，如果无记录则为 0
    next_sequence: int    # 建议的下一个序号 (latest_sequence + 1，最小为 1)
    latest_batch_code: Optional[str] = None  # 最新批次号完整值


@router.get("/latest-sequence", response_model=LatestSequenceResponse, summary="获取最新批次序号")
async def get_latest_sequence(
    furnace_number: str = "03",
    year: Optional[int] = None,
    month: Optional[int] = None
):
    """
    获取指定炉号、年月的最新批次序号
    
    **用途**:
    - 前端开始冶炼弹窗自动填充序号
    - 查询格式: 03-2026-01-XX 中的 XX
    
    **参数**:
    - furnace_number: 炉号，默认 "03"
    - year: 年份，默认当前年
    - month: 月份，默认当前月
    
    **返回**:
    - latest_sequence: 数据库中最新序号，无记录则为 0
    - next_sequence: 建议的下一个序号 (latest + 1，最小为 1)
    """
    from datetime import datetime
    from app.core.influxdb import get_influx_client
    from config import get_settings
    
    settings = get_settings()
    now = datetime.now()
    
    # 默认使用当前年月
    target_year = year if year else now.year
    target_month = month if month else now.month
    
    # 构建批次号前缀: 03-2026-01-
    batch_prefix = f"{furnace_number.zfill(2)}-{target_year}-{str(target_month).zfill(2)}-"
    
    try:
        client = get_influx_client()
        query_api = client.query_api()
        
        # 查询所有匹配前缀的 batch_code（使用 distinct 去重）
        query = f'''
        import "strings"
        
        from(bucket: "{settings.influx_bucket}")
          |> range(start: -{target_year - now.year + 1}y)
          |> filter(fn: (r) => r["_measurement"] == "sensor_data")
          |> filter(fn: (r) => strings.hasPrefix(v: r["batch_code"], prefix: "{batch_prefix}"))
          |> distinct(column: "batch_code")
          |> keep(columns: ["batch_code"])
        '''
        
        result = query_api.query(query)
        
        # 提取所有批次号
        batch_codes = set()
        for table in result:
            for record in table.records:
                batch_code = record.values.get("batch_code")
                if batch_code:
                    batch_codes.add(batch_code)
        
        # 解析序号
        max_sequence = 0
        latest_batch_code = None
        
        for code in batch_codes:
            try:
                # 格式: 03-2026-01-15
                parts = code.split("-")
                if len(parts) == 4:
                    seq = int(parts[3])
                    if seq > max_sequence:
                        max_sequence = seq
                        latest_batch_code = code
            except (ValueError, IndexError):
                continue
        
        return LatestSequenceResponse(
            success=True,
            furnace_number=furnace_number,
            year=target_year,
            month=target_month,
            latest_sequence=max_sequence,
            next_sequence=max_sequence + 1 if max_sequence > 0 else 1,
            latest_batch_code=latest_batch_code
        )
        
    except Exception as e:
        print(f"❌ 查询最新批次序号失败: {e}")
        # 出错时返回默认值
        return LatestSequenceResponse(
            success=False,
            furnace_number=furnace_number,
            year=target_year,
            month=target_month,
            latest_sequence=0,
            next_sequence=1,
            latest_batch_code=None
        )
