from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging

router = APIRouter(tags=["broadcast"])
logger = logging.getLogger(__name__)


# Request/Response Models
class ScheduleRequest(BaseModel):
    """配信スケジュールリクエスト"""
    document_id: int = Field(..., description="IR文書ID")
    publish_time: Optional[datetime] = Field(None, description="公開予定時刻（指定なしで即時）")
    title: Optional[str] = Field(None, description="動画タイトル（指定なしで自動生成）")
    description: Optional[str] = Field(None, description="動画説明")
    tags: Optional[List[str]] = Field(None, description="タグリスト")


class ScheduleResponse(BaseModel):
    """配信スケジュールレスポンス"""
    job_id: str
    status: str
    publish_time: datetime
    title: Optional[str] = None


class JobStatusResponse(BaseModel):
    """ジョブステータスレスポンス"""
    job_id: str
    status: str
    publish_time: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class RescheduleRequest(BaseModel):
    """再スケジュールリクエスト"""
    new_publish_time: datetime


class DailyScheduleRequest(BaseModel):
    """日次スケジュール設定リクエスト"""
    hour: int = Field(20, ge=0, le=23, description="実行時間（時）")
    minute: int = Field(0, ge=0, le=59, description="実行時間（分）")


class UploadRequest(BaseModel):
    """即時アップロードリクエスト"""
    video_path: str = Field(..., description="動画ファイルパス")
    title: str = Field(..., description="動画タイトル")
    description: str = Field(..., description="動画説明")
    tags: Optional[List[str]] = Field(None, description="タグリスト")
    privacy_status: str = Field("unlisted", description="公開ステータス")
    thumbnail_path: Optional[str] = Field(None, description="サムネイル画像パス")


class UploadResponse(BaseModel):
    """アップロードレスポンス"""
    video_id: str
    url: str
    title: str


# Background Tasks
async def generate_and_upload(document_id: int, title: str = None, description: str = None):
    """
    IR文書から動画を生成してアップロード

    Args:
        document_id: IR文書ID
        title: 動画タイトル
        description: 動画説明
    """
    logger.info(f"Starting video generation for document: {document_id}")

    try:
        # TODO: 実装
        # 1. 文書情報を取得
        # 2. LLM分析を実行
        # 3. 台本を生成
        # 4. TTS音声を生成
        # 5. 動画をレンダリング
        # 6. YouTubeにアップロード

        logger.info(f"Video generation completed for document: {document_id}")

    except Exception as e:
        logger.error(f"Video generation failed for document {document_id}: {str(e)}")


# Endpoints
@router.post("/broadcast/schedule", response_model=ScheduleResponse)
async def schedule_broadcast(
    request: ScheduleRequest,
    background_tasks: BackgroundTasks,
):
    """
    IR解説動画の配信をスケジュール

    - document_id: 対象のIR文書ID
    - publish_time: 公開予定時刻（省略時は即時配信処理開始）
    - title: 動画タイトル（省略時は自動生成）
    """
    from app.services.broadcast_scheduler import scheduler

    job_id = f"broadcast_{request.document_id}_{int(datetime.now().timestamp())}"
    publish_time = request.publish_time or datetime.now()

    # 動画生成タスクをバックグラウンドで実行
    background_tasks.add_task(
        generate_and_upload,
        request.document_id,
        request.title,
        request.description,
    )

    logger.info(f"Broadcast scheduled: {job_id}")

    return ScheduleResponse(
        job_id=job_id,
        status="scheduled",
        publish_time=publish_time,
        title=request.title,
    )


@router.get("/broadcast/status/{job_id}", response_model=JobStatusResponse)
async def get_broadcast_status(job_id: str):
    """
    配信ステータスを取得

    - job_id: ジョブID
    """
    from app.services.broadcast_scheduler import scheduler

    job_info = scheduler.get_job_status(job_id)

    if not job_info:
        # ジョブが見つからない場合はpending状態を返す
        return JobStatusResponse(
            job_id=job_id,
            status="pending",
        )

    return JobStatusResponse(
        job_id=job_id,
        status=job_info.get("status", "unknown"),
        publish_time=job_info.get("publish_time"),
        result=job_info.get("result"),
        error=job_info.get("error"),
    )


@router.get("/broadcast/jobs")
async def list_broadcast_jobs():
    """
    全配信ジョブの一覧を取得
    """
    from app.services.broadcast_scheduler import scheduler

    jobs = scheduler.list_jobs()

    return {
        "jobs": [
            {
                "job_id": job_id,
                **{k: str(v) if isinstance(v, datetime) else v for k, v in job_info.items()},
            }
            for job_id, job_info in jobs.items()
        ],
        "total": len(jobs),
    }


@router.post("/broadcast/reschedule/{job_id}", response_model=JobStatusResponse)
async def reschedule_broadcast(job_id: str, request: RescheduleRequest):
    """
    配信を再スケジュール

    - job_id: ジョブID
    - new_publish_time: 新しい公開時刻
    """
    from app.services.broadcast_scheduler import scheduler

    result = scheduler.reschedule_job(job_id, request.new_publish_time)

    if not result:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return JobStatusResponse(
        job_id=job_id,
        status=result.get("status", "rescheduled"),
        publish_time=result.get("publish_time"),
    )


@router.delete("/broadcast/cancel/{job_id}")
async def cancel_broadcast(job_id: str):
    """
    配信をキャンセル

    - job_id: ジョブID
    """
    from app.services.broadcast_scheduler import scheduler

    success = scheduler.cancel_job(job_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"Job not found or already completed: {job_id}")

    return {"message": f"Job {job_id} cancelled successfully"}


@router.post("/broadcast/daily/setup")
async def setup_daily_broadcast(request: DailyScheduleRequest):
    """
    日次自動配信を設定

    - hour: 実行時間（時、0-23）
    - minute: 実行時間（分、0-59）
    """
    from app.services.broadcast_scheduler import scheduler

    job_id = scheduler.schedule_daily_analysis(
        hour=request.hour,
        minute=request.minute,
    )

    return {
        "job_id": job_id,
        "status": "active",
        "schedule": f"{request.hour:02d}:{request.minute:02d} daily",
    }


@router.delete("/broadcast/daily/cancel")
async def cancel_daily_broadcast():
    """
    日次自動配信をキャンセル
    """
    from app.services.broadcast_scheduler import scheduler

    success = scheduler.cancel_job("daily_analysis")

    if not success:
        raise HTTPException(status_code=404, detail="Daily broadcast not configured")

    return {"message": "Daily broadcast cancelled successfully"}


@router.post("/broadcast/upload", response_model=UploadResponse)
async def upload_video_directly(request: UploadRequest):
    """
    動画を即時アップロード

    - video_path: 動画ファイルのパス
    - title: 動画タイトル
    - description: 動画説明
    - tags: タグリスト
    - privacy_status: 公開ステータス (public/private/unlisted)
    - thumbnail_path: サムネイル画像パス
    """
    from app.services.youtube_uploader import YouTubeUploader

    try:
        uploader = YouTubeUploader()
        uploader.authenticate_with_tokens()

        result = uploader.upload_video(
            video_path=request.video_path,
            title=request.title,
            description=request.description,
            tags=request.tags,
            privacy_status=request.privacy_status,
        )

        if request.thumbnail_path:
            uploader.set_thumbnail(result["video_id"], request.thumbnail_path)

        return UploadResponse(
            video_id=result["video_id"],
            url=result["url"],
            title=result["title"],
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"File not found: {str(e)}")
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/broadcast/oauth/init")
async def init_oauth():
    """
    YouTube OAuth認証を開始

    注意: この操作はサーバーサイドでブラウザが必要です。
    開発環境でのみ使用してください。
    """
    from app.services.youtube_uploader import YouTubeUploader

    try:
        uploader = YouTubeUploader()
        uploader.authenticate()
        uploader.save_credentials()

        return {"message": "OAuth authentication completed and credentials saved"}

    except Exception as e:
        logger.error(f"OAuth initialization failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"OAuth failed: {str(e)}")


@router.get("/broadcast/scheduler/status")
async def get_scheduler_status():
    """
    スケジューラーのステータスを取得
    """
    from app.services.broadcast_scheduler import scheduler

    return {
        "running": scheduler.scheduler.running,
        "jobs_count": len(scheduler.jobs),
        "jobs": list(scheduler.jobs.keys()),
    }


@router.post("/broadcast/scheduler/start")
async def start_scheduler():
    """
    スケジューラーを開始
    """
    from app.services.broadcast_scheduler import scheduler

    scheduler.start()

    return {"message": "Scheduler started", "running": scheduler.scheduler.running}


@router.post("/broadcast/scheduler/stop")
async def stop_scheduler():
    """
    スケジューラーを停止
    """
    from app.services.broadcast_scheduler import scheduler

    scheduler.shutdown()

    return {"message": "Scheduler stopped", "running": scheduler.scheduler.running}
