from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from typing import Dict, Any, Optional, Callable
import logging
import asyncio

logger = logging.getLogger(__name__)


class BroadcastScheduler:
    """動画配信スケジューラー"""

    _instance = None

    def __new__(cls):
        """シングルトンパターン"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.scheduler = AsyncIOScheduler()
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self._initialized = True

    def start(self):
        """スケジューラーを開始"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Broadcast scheduler started")

    def shutdown(self):
        """スケジューラーを停止"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Broadcast scheduler stopped")

    def schedule_video_upload(
        self,
        job_id: str,
        video_path: str,
        title: str,
        description: str,
        publish_time: datetime,
        tags: list[str] = None,
        thumbnail_path: str = None,
    ) -> Dict[str, Any]:
        """
        動画アップロードをスケジュール

        Args:
            job_id: ジョブの一意識別子
            video_path: 動画ファイルのパス
            title: 動画タイトル
            description: 動画の説明
            publish_time: 公開予定時刻
            tags: タグのリスト
            thumbnail_path: サムネイル画像のパス

        Returns:
            Dict: ジョブ情報
        """
        from app.services.youtube_uploader import YouTubeUploader

        async def upload_job():
            try:
                logger.info(f"Starting scheduled upload: {job_id}")
                uploader = YouTubeUploader()
                uploader.authenticate_with_tokens()

                result = uploader.upload_video(
                    video_path=video_path,
                    title=title,
                    description=description,
                    tags=tags,
                    privacy_status="private",  # 予約投稿として非公開でアップロード
                )

                if thumbnail_path:
                    uploader.set_thumbnail(result["video_id"], thumbnail_path)

                self.jobs[job_id]["status"] = "completed"
                self.jobs[job_id]["result"] = result
                logger.info(f"Scheduled upload completed: {result['url']}")

            except Exception as e:
                self.jobs[job_id]["status"] = "failed"
                self.jobs[job_id]["error"] = str(e)
                logger.error(f"Scheduled upload failed: {str(e)}")

        self.scheduler.add_job(
            upload_job,
            trigger=DateTrigger(run_date=publish_time),
            id=job_id,
            replace_existing=True,
        )

        self.jobs[job_id] = {
            "status": "scheduled",
            "publish_time": publish_time,
            "video_path": video_path,
            "title": title,
            "created_at": datetime.now(),
        }

        logger.info(f"Video upload scheduled: {job_id} at {publish_time}")
        return self.jobs[job_id]

    def schedule_daily_analysis(
        self,
        hour: int = 20,
        minute: int = 0,
        callback: Callable = None,
    ) -> str:
        """
        毎日の自動配信をスケジュール

        Args:
            hour: 実行時間（時）
            minute: 実行時間（分）
            callback: カスタムコールバック関数

        Returns:
            str: ジョブID
        """
        job_id = "daily_analysis"

        if callback:
            job_func = callback
        else:
            job_func = self._daily_analysis_job

        self.scheduler.add_job(
            job_func,
            trigger=CronTrigger(hour=hour, minute=minute),
            id=job_id,
            replace_existing=True,
        )

        self.jobs[job_id] = {
            "status": "active",
            "schedule": f"{hour:02d}:{minute:02d} daily",
            "type": "recurring",
        }

        logger.info(f"Daily analysis scheduled at {hour:02d}:{minute:02d}")
        return job_id

    async def _daily_analysis_job(self):
        """
        日次分析動画生成・配信ジョブ

        実行フロー:
        1. 最新のIR資料を取得
        2. AI分析・台本生成
        3. TTS音声生成
        4. 動画レンダリング
        5. YouTubeアップロード
        """
        logger.info("Starting daily analysis job")

        try:
            # TODO: 実装
            # 1. 最新のIR資料を取得
            # from app.crawler.tdnet import TDNetCrawler
            # crawler = TDNetCrawler()
            # documents = await crawler.fetch_latest()

            # 2. AI分析・台本生成
            # from app.services.llm_analyzer import LLMAnalyzer
            # from app.services.vtuber_script import VTuberScriptGenerator
            # analyzer = LLMAnalyzer()
            # script_gen = VTuberScriptGenerator()

            # 3. TTS音声生成
            # TODO: TTS service implementation

            # 4. 動画レンダリング
            # TODO: Video rendering implementation

            # 5. YouTubeアップロード
            # from app.services.youtube_uploader import YouTubeUploader
            # uploader = YouTubeUploader()

            logger.info("Daily analysis job completed")

        except Exception as e:
            logger.error(f"Daily analysis job failed: {str(e)}")

    def schedule_weekly_summary(
        self,
        day_of_week: str = "sun",
        hour: int = 18,
        minute: int = 0,
    ) -> str:
        """
        週次サマリー配信をスケジュール

        Args:
            day_of_week: 曜日 (mon, tue, wed, thu, fri, sat, sun)
            hour: 実行時間（時）
            minute: 実行時間（分）

        Returns:
            str: ジョブID
        """
        job_id = "weekly_summary"

        self.scheduler.add_job(
            self._weekly_summary_job,
            trigger=CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute),
            id=job_id,
            replace_existing=True,
        )

        self.jobs[job_id] = {
            "status": "active",
            "schedule": f"{day_of_week} {hour:02d}:{minute:02d}",
            "type": "recurring",
        }

        logger.info(f"Weekly summary scheduled on {day_of_week} at {hour:02d}:{minute:02d}")
        return job_id

    async def _weekly_summary_job(self):
        """週次サマリー動画生成・配信ジョブ"""
        logger.info("Starting weekly summary job")
        # TODO: 週次サマリーの実装
        pass

    def cancel_job(self, job_id: str) -> bool:
        """
        ジョブをキャンセル

        Args:
            job_id: キャンセルするジョブのID

        Returns:
            bool: 成功したかどうか
        """
        try:
            self.scheduler.remove_job(job_id)
            if job_id in self.jobs:
                self.jobs[job_id]["status"] = "cancelled"
            logger.info(f"Job cancelled: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel job {job_id}: {str(e)}")
            return False

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        ジョブのステータスを取得

        Args:
            job_id: ジョブID

        Returns:
            Optional[Dict]: ジョブ情報
        """
        return self.jobs.get(job_id)

    def list_jobs(self) -> Dict[str, Dict[str, Any]]:
        """
        全ジョブの一覧を取得

        Returns:
            Dict: 全ジョブ情報
        """
        return self.jobs

    def reschedule_job(
        self,
        job_id: str,
        new_publish_time: datetime,
    ) -> Optional[Dict[str, Any]]:
        """
        ジョブを再スケジュール

        Args:
            job_id: ジョブID
            new_publish_time: 新しい公開時刻

        Returns:
            Optional[Dict]: 更新されたジョブ情報
        """
        if job_id not in self.jobs:
            return None

        try:
            self.scheduler.reschedule_job(
                job_id,
                trigger=DateTrigger(run_date=new_publish_time),
            )
            self.jobs[job_id]["publish_time"] = new_publish_time
            self.jobs[job_id]["updated_at"] = datetime.now()
            logger.info(f"Job rescheduled: {job_id} to {new_publish_time}")
            return self.jobs[job_id]
        except Exception as e:
            logger.error(f"Failed to reschedule job {job_id}: {str(e)}")
            return None


# グローバルスケジューラーインスタンス
scheduler = BroadcastScheduler()
