"""
スケジューラーAPI
定期バッチジョブの管理エンドポイント
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Optional
from pydantic import BaseModel

from app.services.scheduler_service import (
    scheduler_service,
    SchedulerStatus,
    ScheduledJobInfo,
    JobLog,
)

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


class SchedulerActionResponse(BaseModel):
    """スケジューラー操作レスポンス"""
    success: bool
    message: str


class TriggerJobRequest(BaseModel):
    """ジョブトリガーリクエスト"""
    job_id: str


@router.get("/status", response_model=SchedulerStatus)
async def get_scheduler_status():
    """
    スケジューラーのステータスを取得

    Returns:
        スケジューラーのステータス（実行中かどうか、ジョブ一覧、最新ログ）
    """
    return scheduler_service.get_status()


@router.post("/start", response_model=SchedulerActionResponse)
async def start_scheduler():
    """
    スケジューラーを開始

    Returns:
        操作結果
    """
    try:
        scheduler_service.start()
        return SchedulerActionResponse(
            success=True,
            message="Scheduler started successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop", response_model=SchedulerActionResponse)
async def stop_scheduler():
    """
    スケジューラーを停止

    Returns:
        操作結果
    """
    try:
        scheduler_service.stop()
        return SchedulerActionResponse(
            success=True,
            message="Scheduler stopped successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pause", response_model=SchedulerActionResponse)
async def pause_scheduler():
    """
    スケジューラーを一時停止（全ジョブ）

    Returns:
        操作結果
    """
    try:
        scheduler_service.pause()
        return SchedulerActionResponse(
            success=True,
            message="Scheduler paused successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resume", response_model=SchedulerActionResponse)
async def resume_scheduler():
    """
    スケジューラーを再開（全ジョブ）

    Returns:
        操作結果
    """
    try:
        scheduler_service.resume()
        return SchedulerActionResponse(
            success=True,
            message="Scheduler resumed successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs", response_model=List[ScheduledJobInfo])
async def get_jobs():
    """
    登録されているジョブ一覧を取得

    Returns:
        ジョブ一覧
    """
    status = scheduler_service.get_status()
    return status.jobs


@router.get("/jobs/{job_id}", response_model=ScheduledJobInfo)
async def get_job(job_id: str):
    """
    特定のジョブ情報を取得

    Args:
        job_id: ジョブID

    Returns:
        ジョブ情報
    """
    job = scheduler_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job


@router.post("/jobs/{job_id}/pause", response_model=SchedulerActionResponse)
async def pause_job(job_id: str):
    """
    特定のジョブを一時停止

    Args:
        job_id: ジョブID

    Returns:
        操作結果
    """
    success = scheduler_service.pause_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return SchedulerActionResponse(
        success=True,
        message=f"Job {job_id} paused successfully"
    )


@router.post("/jobs/{job_id}/resume", response_model=SchedulerActionResponse)
async def resume_job(job_id: str):
    """
    特定のジョブを再開

    Args:
        job_id: ジョブID

    Returns:
        操作結果
    """
    success = scheduler_service.resume_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return SchedulerActionResponse(
        success=True,
        message=f"Job {job_id} resumed successfully"
    )


@router.post("/jobs/{job_id}/trigger", response_model=SchedulerActionResponse)
async def trigger_job(job_id: str, background_tasks: BackgroundTasks):
    """
    特定のジョブを手動でトリガー（即座に実行）

    Args:
        job_id: ジョブID

    Returns:
        操作結果
    """
    # バックグラウンドで実行
    async def run_job():
        await scheduler_service.trigger_job(job_id)

    background_tasks.add_task(run_job)

    return SchedulerActionResponse(
        success=True,
        message=f"Job {job_id} triggered successfully (running in background)"
    )


@router.get("/logs", response_model=List[JobLog])
async def get_logs(
    job_id: Optional[str] = None,
    limit: int = 50
):
    """
    ジョブ実行ログを取得

    Args:
        job_id: 特定のジョブIDでフィルタ（オプション）
        limit: 取得件数（デフォルト50）

    Returns:
        ジョブ実行ログ一覧
    """
    return scheduler_service.get_logs(job_id=job_id, limit=limit)


@router.delete("/logs", response_model=SchedulerActionResponse)
async def clear_logs():
    """
    ジョブ実行ログをクリア

    Returns:
        操作結果
    """
    scheduler_service.clear_logs()
    return SchedulerActionResponse(
        success=True,
        message="Job logs cleared successfully"
    )
