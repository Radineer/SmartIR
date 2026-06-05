"""
配信API
IR解説動画の生成・配信スケジュール管理
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.broadcast import BroadcastJob, BroadcastStatus
from app.models.document import Document

router = APIRouter(tags=["broadcast"])
logger = logging.getLogger(__name__)


# ===== Request/Response Models =====


class ScheduleRequest(BaseModel):
    """配信スケジュールリクエスト"""
    document_id: int = Field(..., description="IR文書ID")
    publish_time: Optional[datetime] = Field(None, description="公開予定時刻（指定なしで即時）")
    title: Optional[str] = Field(None, description="動画タイトル（指定なしで自動生成）")
    description: Optional[str] = Field(None, description="動画説明")
    tags: Optional[List[str]] = Field(None, description="タグリスト")


class ScheduleResponse(BaseModel):
    """配信スケジュールレスポンス"""
    job_id: int
    status: str
    publish_time: Optional[datetime] = None
    title: Optional[str] = None


class JobStatusResponse(BaseModel):
    """ジョブステータスレスポンス"""
    job_id: int
    status: str
    document_id: Optional[int] = None
    publish_time: Optional[datetime] = None
    title: Optional[str] = None
    video_id: Optional[str] = None
    video_url: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class JobListResponse(BaseModel):
    """ジョブ一覧レスポンス"""
    jobs: List[JobStatusResponse]
    total: int


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
    job_id: int
    video_id: str
    url: str
    title: str


# ===== Helper Functions =====


def _job_to_response(job: BroadcastJob) -> JobStatusResponse:
    """BroadcastJobモデルをレスポンスに変換"""
    return JobStatusResponse(
        job_id=job.id,
        status=job.status.value if isinstance(job.status, BroadcastStatus) else job.status,
        document_id=job.document_id,
        publish_time=job.publish_time,
        title=job.title,
        video_id=job.video_id,
        video_url=job.video_url,
        result=job.result,
        error=job.error_message,
        created_at=job.created_at.isoformat() if job.created_at else None,
        updated_at=job.updated_at.isoformat() if job.updated_at else None,
    )


# ===== Background Tasks =====


def _get_db_session():
    """バックグラウンドタスク用にDB sessionを新規取得"""
    from app.core.database import SessionLocal
    return SessionLocal()


async def generate_and_upload(job_id: int):
    """
    IR文書から動画を生成してアップロード

    Args:
        job_id: BroadcastJobのDB ID
    """
    db = _get_db_session()
    try:
        job = db.query(BroadcastJob).filter(BroadcastJob.id == job_id).first()
        if not job:
            logger.error(f"BroadcastJob not found: {job_id}")
            return

        # ステータスを生成中に更新
        job.status = BroadcastStatus.GENERATING
        db.commit()

        logger.info(f"Starting video generation for job {job_id}, document {job.document_id}")

        # 1. 文書情報を取得
        document = db.query(Document).filter(Document.id == job.document_id).first()
        if not document:
            job.status = BroadcastStatus.FAILED
            job.error_message = f"Document not found: {job.document_id}"
            db.commit()
            return

        # 2. タイトル自動生成（未指定の場合）
        if not job.title:
            job.title = f"IR解説: {document.title}"
            db.commit()

        # 3. LLM分析・台本生成
        try:
            from app.services.llm_analyzer import LLMAnalyzer
            analyzer = LLMAnalyzer()
            analysis = await analyzer.analyze_document(document.raw_text or "")
        except ImportError:
            logger.warning("LLMAnalyzer not available, using document text directly")
            analysis = {"summary": document.raw_text or document.title}
        except Exception as e:
            logger.warning(f"LLM analysis failed, continuing with basic content: {e}")
            analysis = {"summary": document.raw_text or document.title}

        # 4. TTS音声生成
        audio_path = None
        try:
            from app.services.talking_avatar import generate_speech
            script_text = analysis.get("summary", document.title) if isinstance(analysis, dict) else str(analysis)
            audio_path = await generate_speech(script_text)
        except ImportError:
            logger.warning("TTS service not available, skipping audio generation")
        except Exception as e:
            logger.warning(f"TTS generation failed: {e}")

        # 5. 動画レンダリング
        video_path = job.video_path
        if not video_path:
            try:
                from app.services.video_renderer import render_video
                video_path = await render_video(
                    document=document,
                    analysis=analysis,
                    audio_path=audio_path,
                )
                job.video_path = video_path
                db.commit()
            except ImportError:
                logger.warning("Video renderer not available")
                job.status = BroadcastStatus.FAILED
                job.error_message = "Video renderer service not available"
                db.commit()
                return
            except Exception as e:
                job.status = BroadcastStatus.FAILED
                job.error_message = f"Video rendering failed: {str(e)}"
                db.commit()
                return

        # 6. YouTubeにアップロード
        job.status = BroadcastStatus.UPLOADING
        db.commit()

        try:
            from app.services.youtube_uploader import YouTubeUploader
            uploader = YouTubeUploader()
            uploader.authenticate_with_tokens()

            result = uploader.upload_video(
                video_path=video_path,
                title=job.title,
                description=job.description or f"IR文書「{document.title}」の解説動画",
                tags=job.tags,
                privacy_status="unlisted",
            )

            if job.thumbnail_path:
                uploader.set_thumbnail(result["video_id"], job.thumbnail_path)

            job.status = BroadcastStatus.COMPLETED
            job.video_id = result["video_id"]
            job.video_url = result["url"]
            job.result = result
            db.commit()

            logger.info(f"Video generation completed for job {job_id}: {result['url']}")

        except Exception as e:
            job.status = BroadcastStatus.FAILED
            job.error_message = f"Upload failed: {str(e)}"
            db.commit()
            logger.error(f"Upload failed for job {job_id}: {str(e)}")

    except Exception as e:
        logger.error(f"Video generation failed for job {job_id}: {str(e)}")
        try:
            job = db.query(BroadcastJob).filter(BroadcastJob.id == job_id).first()
            if job:
                job.status = BroadcastStatus.FAILED
                job.error_message = f"Unexpected error: {str(e)}"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


async def upload_video_task(job_id: int):
    """
    既存の動画を即時アップロード

    Args:
        job_id: BroadcastJobのDB ID
    """
    db = _get_db_session()
    try:
        job = db.query(BroadcastJob).filter(BroadcastJob.id == job_id).first()
        if not job:
            logger.error(f"BroadcastJob not found: {job_id}")
            return

        job.status = BroadcastStatus.UPLOADING
        db.commit()

        from app.services.youtube_uploader import YouTubeUploader
        uploader = YouTubeUploader()
        uploader.authenticate_with_tokens()

        result = uploader.upload_video(
            video_path=job.video_path,
            title=job.title,
            description=job.description or "",
            tags=job.tags,
            privacy_status=job.privacy_status or "unlisted",
        )

        if job.thumbnail_path:
            uploader.set_thumbnail(result["video_id"], job.thumbnail_path)

        job.status = BroadcastStatus.COMPLETED
        job.video_id = result["video_id"]
        job.video_url = result["url"]
        job.result = result
        db.commit()

        logger.info(f"Direct upload completed for job {job_id}: {result['url']}")

    except FileNotFoundError as e:
        job.status = BroadcastStatus.FAILED
        job.error_message = f"File not found: {str(e)}"
        db.commit()
        logger.error(f"Upload failed for job {job_id}: file not found")
    except Exception as e:
        logger.error(f"Upload failed for job {job_id}: {str(e)}")
        try:
            job = db.query(BroadcastJob).filter(BroadcastJob.id == job_id).first()
            if job:
                job.status = BroadcastStatus.FAILED
                job.error_message = f"Upload failed: {str(e)}"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


# ===== API Endpoints =====


@router.post("/broadcast/schedule", response_model=ScheduleResponse)
async def schedule_broadcast(
    request: ScheduleRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    IR解説動画の配信をスケジュール

    - document_id: 対象のIR文書ID
    - publish_time: 公開予定時刻（省略時は即時配信処理開始）
    - title: 動画タイトル（省略時は自動生成）
    """
    # 文書の存在確認
    document = db.query(Document).filter(Document.id == request.document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail=f"Document not found: {request.document_id}")

    publish_time = request.publish_time or datetime.utcnow()
    is_immediate = request.publish_time is None

    # DBにジョブを作成
    job = BroadcastJob(
        user_id=current_user.id,
        document_id=request.document_id,
        title=request.title,
        description=request.description,
        tags=request.tags,
        publish_time=publish_time,
        status=BroadcastStatus.PENDING if not is_immediate else BroadcastStatus.SCHEDULED,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    if is_immediate:
        # 即時実行: バックグラウンドタスクで動画生成・アップロード
        background_tasks.add_task(generate_and_upload, job.id)
        logger.info(f"Immediate broadcast started: job_id={job.id}")
    else:
        # 予約実行: APSchedulerに登録
        try:
            from app.services.broadcast_scheduler import scheduler
            scheduler_job_id = f"broadcast_{job.id}"

            scheduler.schedule_video_upload(
                job_id=scheduler_job_id,
                video_path="",  # 生成後に設定される
                title=request.title or "",
                description=request.description or "",
                publish_time=publish_time,
                tags=request.tags,
            )

            job.status = BroadcastStatus.SCHEDULED
            db.commit()
            logger.info(f"Broadcast scheduled: job_id={job.id} at {publish_time}")
        except Exception as e:
            # スケジューラ登録に失敗した場合はバックグラウンドで即時実行にフォールバック
            logger.warning(f"Scheduler registration failed, falling back to immediate: {e}")
            background_tasks.add_task(generate_and_upload, job.id)

    return ScheduleResponse(
        job_id=job.id,
        status=job.status.value,
        publish_time=publish_time,
        title=request.title,
    )


@router.post("/broadcast/upload", response_model=UploadResponse)
async def upload_video_directly(
    request: UploadRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    動画を即時アップロード

    - video_path: 動画ファイルのパス
    - title: 動画タイトル
    - description: 動画説明
    - tags: タグリスト
    - privacy_status: 公開ステータス (public/private/unlisted)
    - thumbnail_path: サムネイル画像パス
    """
    import os
    if not os.path.exists(request.video_path):
        raise HTTPException(status_code=404, detail=f"Video file not found: {request.video_path}")

    # DBにジョブを作成
    job = BroadcastJob(
        user_id=current_user.id,
        title=request.title,
        description=request.description,
        tags=request.tags,
        privacy_status=request.privacy_status,
        video_path=request.video_path,
        thumbnail_path=request.thumbnail_path,
        status=BroadcastStatus.PENDING,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # バックグラウンドでアップロード実行
    background_tasks.add_task(upload_video_task, job.id)

    logger.info(f"Direct upload queued: job_id={job.id}")

    return UploadResponse(
        job_id=job.id,
        video_id="pending",
        url="pending",
        title=request.title,
    )


@router.get("/broadcast/jobs/{job_id}", response_model=JobStatusResponse)
async def get_broadcast_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    配信ジョブの詳細ステータスを取得

    - job_id: ジョブID（DB上のID）
    """
    job = db.query(BroadcastJob).filter(
        BroadcastJob.id == job_id,
        BroadcastJob.user_id == current_user.id,
    ).first()

    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return _job_to_response(job)


@router.delete("/broadcast/jobs/{job_id}")
async def delete_broadcast_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    配信ジョブを削除（完了・失敗・キャンセル済みのみ削除可能）

    - job_id: ジョブID
    """
    job = db.query(BroadcastJob).filter(
        BroadcastJob.id == job_id,
        BroadcastJob.user_id == current_user.id,
    ).first()

    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    # 実行中のジョブは削除不可
    active_statuses = {BroadcastStatus.PENDING, BroadcastStatus.SCHEDULED, BroadcastStatus.GENERATING, BroadcastStatus.UPLOADING}
    if job.status in active_statuses:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete active job (status: {job.status.value}). Cancel it first.",
        )

    db.delete(job)
    db.commit()

    return {"message": f"Job {job_id} deleted successfully", "id": job_id}


@router.get("/broadcast/jobs", response_model=JobListResponse)
async def list_broadcast_jobs(
    status: Optional[str] = Query(None, description="ステータスでフィルタ"),
    limit: int = Query(20, ge=1, le=100, description="取得件数"),
    offset: int = Query(0, ge=0, description="オフセット"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    全配信ジョブの一覧を取得（認証ユーザーのジョブのみ）
    """
    query = db.query(BroadcastJob).filter(BroadcastJob.user_id == current_user.id)

    if status:
        try:
            status_enum = BroadcastStatus(status)
            query = query.filter(BroadcastJob.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}. Valid: {[s.value for s in BroadcastStatus]}",
            )

    total = query.count()
    jobs = query.order_by(BroadcastJob.created_at.desc()).offset(offset).limit(limit).all()

    return JobListResponse(
        jobs=[_job_to_response(job) for job in jobs],
        total=total,
    )


@router.post("/broadcast/jobs/{job_id}/cancel")
async def cancel_broadcast(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    配信ジョブをキャンセル

    - job_id: ジョブID
    """
    job = db.query(BroadcastJob).filter(
        BroadcastJob.id == job_id,
        BroadcastJob.user_id == current_user.id,
    ).first()

    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    terminal_statuses = {BroadcastStatus.COMPLETED, BroadcastStatus.FAILED, BroadcastStatus.CANCELLED}
    if job.status in terminal_statuses:
        raise HTTPException(
            status_code=409,
            detail=f"Job already in terminal state: {job.status.value}",
        )

    # APSchedulerからも削除を試みる
    try:
        from app.services.broadcast_scheduler import scheduler
        scheduler_job_id = f"broadcast_{job.id}"
        scheduler.cancel_job(scheduler_job_id)
    except Exception as e:
        logger.debug(f"Scheduler cancel for job {job_id} skipped: {e}")

    job.status = BroadcastStatus.CANCELLED
    db.commit()

    return {"message": f"Job {job_id} cancelled successfully", "id": job_id}


@router.post("/broadcast/jobs/{job_id}/reschedule", response_model=JobStatusResponse)
async def reschedule_broadcast(
    job_id: int,
    request: RescheduleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    配信を再スケジュール

    - job_id: ジョブID
    - new_publish_time: 新しい公開時刻
    """
    job = db.query(BroadcastJob).filter(
        BroadcastJob.id == job_id,
        BroadcastJob.user_id == current_user.id,
    ).first()

    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    # 完了済み・失敗済みは再スケジュール不可
    if job.status in {BroadcastStatus.COMPLETED, BroadcastStatus.FAILED}:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot reschedule job in state: {job.status.value}",
        )

    if request.new_publish_time <= datetime.utcnow():
        raise HTTPException(
            status_code=400,
            detail="New publish time must be in the future",
        )

    # APSchedulerを更新
    try:
        from app.services.broadcast_scheduler import scheduler
        scheduler_job_id = f"broadcast_{job.id}"
        scheduler.reschedule_job(scheduler_job_id, request.new_publish_time)
    except Exception as e:
        logger.debug(f"Scheduler reschedule for job {job_id} skipped: {e}")

    job.publish_time = request.new_publish_time
    job.status = BroadcastStatus.SCHEDULED
    db.commit()
    db.refresh(job)

    return _job_to_response(job)


@router.post("/broadcast/daily/setup")
async def setup_daily_broadcast(
    request: DailyScheduleRequest,
    current_user: User = Depends(get_current_user),
):
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
async def cancel_daily_broadcast(
    current_user: User = Depends(get_current_user),
):
    """
    日次自動配信をキャンセル
    """
    from app.services.broadcast_scheduler import scheduler

    success = scheduler.cancel_job("daily_analysis")

    if not success:
        raise HTTPException(status_code=404, detail="Daily broadcast not configured")

    return {"message": "Daily broadcast cancelled successfully"}


@router.post("/broadcast/upload/direct", response_model=UploadResponse)
async def upload_video_sync(
    request: UploadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    動画を同期的にアップロード（即時結果返却）

    バックグラウンドではなく、レスポンス返却前にアップロードを完了する。
    小さいファイルや確実に結果を受け取りたい場合に使用。
    """
    import os
    if not os.path.exists(request.video_path):
        raise HTTPException(status_code=404, detail=f"Video file not found: {request.video_path}")

    try:
        from app.services.youtube_uploader import YouTubeUploader
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

        # DBに完了済みジョブとして記録
        job = BroadcastJob(
            user_id=current_user.id,
            title=request.title,
            description=request.description,
            tags=request.tags,
            privacy_status=request.privacy_status,
            video_path=request.video_path,
            thumbnail_path=request.thumbnail_path,
            status=BroadcastStatus.COMPLETED,
            video_id=result["video_id"],
            video_url=result["url"],
            result=result,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        return UploadResponse(
            job_id=job.id,
            video_id=result["video_id"],
            url=result["url"],
            title=result["title"],
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"File not found: {str(e)}")
    except Exception as e:
        logger.error(f"Sync upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/broadcast/oauth/init")
async def init_oauth(
    current_user: User = Depends(get_current_user),
):
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
async def get_scheduler_status(
    current_user: User = Depends(get_current_user),
):
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
async def start_scheduler(
    current_user: User = Depends(get_current_user),
):
    """
    スケジューラーを開始
    """
    from app.services.broadcast_scheduler import scheduler

    scheduler.start()

    return {"message": "Scheduler started", "running": scheduler.scheduler.running}


@router.post("/broadcast/scheduler/stop")
async def stop_scheduler(
    current_user: User = Depends(get_current_user),
):
    """
    スケジューラーを停止
    """
    from app.services.broadcast_scheduler import scheduler

    scheduler.shutdown()

    return {"message": "Scheduler stopped", "running": scheduler.scheduler.running}
