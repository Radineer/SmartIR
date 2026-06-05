"""
定期バッチジョブスケジューラーサービス
APSchedulerを使用して定期的なバッチ処理を管理
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from pydantic import BaseModel
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.job import Job
from apscheduler.events import (
    EVENT_JOB_EXECUTED,
    EVENT_JOB_ERROR,
    EVENT_JOB_MISSED,
    JobExecutionEvent,
)

from app.core.database import SessionLocal

logger = logging.getLogger(__name__)

# タイムゾーン設定
JST = ZoneInfo("Asia/Tokyo")


class JobStatus(str, Enum):
    """ジョブステータス"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    MISSED = "missed"


class JobLog(BaseModel):
    """ジョブ実行ログ"""
    job_id: str
    job_name: str
    status: JobStatus
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    result: Optional[str] = None
    error: Optional[str] = None


class ScheduledJobInfo(BaseModel):
    """スケジュールされたジョブ情報"""
    job_id: str
    job_name: str
    trigger_type: str
    trigger_info: str
    next_run_time: Optional[str] = None
    is_paused: bool = False


class SchedulerStatus(BaseModel):
    """スケジューラーステータス"""
    is_running: bool
    jobs_count: int
    jobs: List[ScheduledJobInfo]
    recent_logs: List[JobLog]


class SchedulerService:
    """
    定期バッチジョブスケジューラーサービス

    ジョブ一覧:
    - ML予測の定期更新（毎日9:00 JST）
    - センチメント分析の定期更新（毎日9:00, 15:00 JST）
    - ウォッチリストアラートのチェック（5分ごと）
    - 市場データのキャッシュ更新（1時間ごと）
    """

    def __init__(self):
        self.scheduler: Optional[AsyncIOScheduler] = None
        self._job_logs: List[JobLog] = []
        self._max_logs = 100  # 保持する最大ログ数
        self._running_jobs: Dict[str, datetime] = {}

    def _add_log(self, log: JobLog):
        """ログを追加（最大件数を超えたら古いものを削除）"""
        self._job_logs.insert(0, log)
        if len(self._job_logs) > self._max_logs:
            self._job_logs = self._job_logs[:self._max_logs]

    def _on_job_executed(self, event: JobExecutionEvent):
        """ジョブ実行完了時のコールバック"""
        job_id = event.job_id
        started_at = self._running_jobs.pop(job_id, None)
        finished_at = datetime.now(JST)

        duration = None
        if started_at:
            duration = (finished_at - started_at).total_seconds()

        log = JobLog(
            job_id=job_id,
            job_name=self._get_job_name(job_id),
            status=JobStatus.COMPLETED,
            started_at=started_at.isoformat() if started_at else None,
            finished_at=finished_at.isoformat(),
            duration_seconds=duration,
            result="Success"
        )
        self._add_log(log)
        logger.info(f"Job {job_id} completed successfully in {duration:.2f}s" if duration else f"Job {job_id} completed")

    def _on_job_error(self, event: JobExecutionEvent):
        """ジョブエラー時のコールバック"""
        job_id = event.job_id
        started_at = self._running_jobs.pop(job_id, None)
        finished_at = datetime.now(JST)

        duration = None
        if started_at:
            duration = (finished_at - started_at).total_seconds()

        error_message = str(event.exception) if event.exception else "Unknown error"

        log = JobLog(
            job_id=job_id,
            job_name=self._get_job_name(job_id),
            status=JobStatus.FAILED,
            started_at=started_at.isoformat() if started_at else None,
            finished_at=finished_at.isoformat(),
            duration_seconds=duration,
            error=error_message
        )
        self._add_log(log)
        logger.error(f"Job {job_id} failed: {error_message}")

    def _on_job_missed(self, event: JobExecutionEvent):
        """ジョブミス時のコールバック"""
        job_id = event.job_id
        log = JobLog(
            job_id=job_id,
            job_name=self._get_job_name(job_id),
            status=JobStatus.MISSED,
            finished_at=datetime.now(JST).isoformat(),
            error="Job execution was missed"
        )
        self._add_log(log)
        logger.warning(f"Job {job_id} was missed")

    def _get_job_name(self, job_id: str) -> str:
        """ジョブIDから名前を取得"""
        job_names = {
            "ml_prediction_update": "ML予測更新",
            "sentiment_analysis_morning": "センチメント分析（朝）",
            "sentiment_analysis_afternoon": "センチメント分析（午後）",
            "watchlist_alert_check": "ウォッチリストアラートチェック",
            "market_data_cache_refresh": "市場データキャッシュ更新",
        }
        return job_names.get(job_id, job_id)

    async def _run_ml_prediction_update(self):
        """ML予測の定期更新ジョブ"""
        from app.services.ml_predictor import ml_predictor_service

        job_id = "ml_prediction_update"
        self._running_jobs[job_id] = datetime.now(JST)

        logger.info("Starting ML prediction update job")

        try:
            # 訓練済みモデル一覧を取得
            models = await ml_predictor_service.list_models()

            updated_count = 0
            for model_info in models:
                ticker = model_info.ticker
                try:
                    # モデルを再訓練
                    await ml_predictor_service.train_model(ticker)
                    updated_count += 1
                    logger.info(f"Updated ML model for {ticker}")
                except Exception as e:
                    logger.error(f"Failed to update ML model for {ticker}: {e}")

            logger.info(f"ML prediction update completed: {updated_count}/{len(models)} models updated")

        except Exception as e:
            logger.error(f"ML prediction update job failed: {e}")
            raise

    async def _run_sentiment_analysis(self):
        """センチメント分析の定期更新ジョブ"""
        from app.services.market_sentiment import market_sentiment_analyzer

        job_id = "sentiment_analysis"
        self._running_jobs[job_id] = datetime.now(JST)

        logger.info("Starting sentiment analysis job")

        try:
            # 恐怖・強欲指数を更新
            market_sentiment = await market_sentiment_analyzer.calculate_fear_greed_index()
            logger.info(f"Fear/Greed Index updated: {market_sentiment.fear_greed_index} ({market_sentiment.market_mood})")

            # 主要銘柄のセンチメントを分析
            from app.services.market_data import MAJOR_JP_STOCKS

            analyzed_count = 0
            for symbol in list(MAJOR_JP_STOCKS.keys())[:5]:  # 上位5銘柄のみ
                try:
                    sentiment = await market_sentiment_analyzer.analyze_news_sentiment(symbol)
                    analyzed_count += 1
                    logger.info(f"Sentiment for {symbol}: {sentiment.overall}")
                except Exception as e:
                    logger.error(f"Failed to analyze sentiment for {symbol}: {e}")

            logger.info(f"Sentiment analysis completed: {analyzed_count} stocks analyzed")

        except Exception as e:
            logger.error(f"Sentiment analysis job failed: {e}")
            raise

    async def _run_watchlist_alert_check(self):
        """ウォッチリストアラートのチェックジョブ"""
        from app.services.watchlist_service import watchlist_service

        job_id = "watchlist_alert_check"
        self._running_jobs[job_id] = datetime.now(JST)

        logger.info("Starting watchlist alert check job")

        try:
            # データベースセッションを作成
            db = SessionLocal()
            try:
                triggered_alerts = watchlist_service.check_alerts(db)

                if triggered_alerts:
                    logger.info(f"Triggered {len(triggered_alerts)} alerts:")
                    for alert in triggered_alerts:
                        logger.info(f"  - {alert.ticker_code}: {alert.alert_type.value} at {alert.current_price}")
                else:
                    logger.debug("No alerts triggered")

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Watchlist alert check job failed: {e}")
            raise

    async def _run_market_data_cache_refresh(self):
        """市場データのキャッシュ更新ジョブ"""
        from app.services.market_data import market_data_service, MAJOR_INDICES, CURRENCY_PAIRS, MAJOR_JP_STOCKS

        job_id = "market_data_cache_refresh"
        self._running_jobs[job_id] = datetime.now(JST)

        logger.info("Starting market data cache refresh job")

        try:
            # キャッシュをクリア
            market_data_service._cache.clear()

            # 主要指数を再取得
            indices = market_data_service.get_indices()
            logger.info(f"Refreshed {len(indices)} indices")

            # 通貨ペアを再取得
            currencies = market_data_service.get_currencies()
            logger.info(f"Refreshed {len(currencies)} currency pairs")

            # 主要日本株を再取得
            stocks = market_data_service.get_major_jp_stocks()
            logger.info(f"Refreshed {len(stocks)} major JP stocks")

            total = len(indices) + len(currencies) + len(stocks)
            logger.info(f"Market data cache refresh completed: {total} items refreshed")

        except Exception as e:
            logger.error(f"Market data cache refresh job failed: {e}")
            raise

    def initialize(self):
        """スケジューラーを初期化（ジョブを登録）"""
        if self.scheduler is not None:
            logger.warning("Scheduler already initialized")
            return

        self.scheduler = AsyncIOScheduler(timezone=JST)

        # イベントリスナーを登録
        self.scheduler.add_listener(self._on_job_executed, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._on_job_error, EVENT_JOB_ERROR)
        self.scheduler.add_listener(self._on_job_missed, EVENT_JOB_MISSED)

        # ジョブを登録
        # 1. ML予測の定期更新（毎日9:00 JST）
        self.scheduler.add_job(
            self._run_ml_prediction_update,
            CronTrigger(hour=9, minute=0, timezone=JST),
            id="ml_prediction_update",
            name="ML予測更新",
            replace_existing=True,
            misfire_grace_time=3600  # 1時間の猶予
        )

        # 2. センチメント分析の定期更新（毎日9:00 JST）
        self.scheduler.add_job(
            self._run_sentiment_analysis,
            CronTrigger(hour=9, minute=0, timezone=JST),
            id="sentiment_analysis_morning",
            name="センチメント分析（朝）",
            replace_existing=True,
            misfire_grace_time=3600
        )

        # 3. センチメント分析の定期更新（毎日15:00 JST）
        self.scheduler.add_job(
            self._run_sentiment_analysis,
            CronTrigger(hour=15, minute=0, timezone=JST),
            id="sentiment_analysis_afternoon",
            name="センチメント分析（午後）",
            replace_existing=True,
            misfire_grace_time=3600
        )

        # 4. ウォッチリストアラートのチェック（5分ごと）
        self.scheduler.add_job(
            self._run_watchlist_alert_check,
            IntervalTrigger(minutes=5, timezone=JST),
            id="watchlist_alert_check",
            name="ウォッチリストアラートチェック",
            replace_existing=True,
            misfire_grace_time=300  # 5分の猶予
        )

        # 5. 市場データのキャッシュ更新（1時間ごと）
        self.scheduler.add_job(
            self._run_market_data_cache_refresh,
            IntervalTrigger(hours=1, timezone=JST),
            id="market_data_cache_refresh",
            name="市場データキャッシュ更新",
            replace_existing=True,
            misfire_grace_time=1800  # 30分の猶予
        )

        logger.info("Scheduler initialized with 5 jobs")

    def start(self):
        """スケジューラーを開始"""
        if self.scheduler is None:
            self.initialize()

        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started")
        else:
            logger.warning("Scheduler is already running")

    def stop(self):
        """スケジューラーを停止"""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")
        else:
            logger.warning("Scheduler is not running")

    def pause(self):
        """スケジューラーを一時停止"""
        if self.scheduler and self.scheduler.running:
            self.scheduler.pause()
            logger.info("Scheduler paused")

    def resume(self):
        """スケジューラーを再開"""
        if self.scheduler:
            self.scheduler.resume()
            logger.info("Scheduler resumed")

    def get_status(self) -> SchedulerStatus:
        """スケジューラーのステータスを取得"""
        is_running = self.scheduler.running if self.scheduler else False

        jobs = []
        if self.scheduler:
            for job in self.scheduler.get_jobs():
                trigger_type = type(job.trigger).__name__

                if isinstance(job.trigger, CronTrigger):
                    trigger_info = str(job.trigger)
                elif isinstance(job.trigger, IntervalTrigger):
                    interval = job.trigger.interval
                    trigger_info = f"Every {interval}"
                else:
                    trigger_info = str(job.trigger)

                next_run = job.next_run_time.isoformat() if job.next_run_time else None

                jobs.append(ScheduledJobInfo(
                    job_id=job.id,
                    job_name=job.name or job.id,
                    trigger_type=trigger_type,
                    trigger_info=trigger_info,
                    next_run_time=next_run,
                    is_paused=job.next_run_time is None
                ))

        return SchedulerStatus(
            is_running=is_running,
            jobs_count=len(jobs),
            jobs=jobs,
            recent_logs=self._job_logs[:20]  # 最新20件のログ
        )

    def get_job(self, job_id: str) -> Optional[ScheduledJobInfo]:
        """特定のジョブ情報を取得"""
        if not self.scheduler:
            return None

        job = self.scheduler.get_job(job_id)
        if not job:
            return None

        trigger_type = type(job.trigger).__name__

        if isinstance(job.trigger, CronTrigger):
            trigger_info = str(job.trigger)
        elif isinstance(job.trigger, IntervalTrigger):
            interval = job.trigger.interval
            trigger_info = f"Every {interval}"
        else:
            trigger_info = str(job.trigger)

        next_run = job.next_run_time.isoformat() if job.next_run_time else None

        return ScheduledJobInfo(
            job_id=job.id,
            job_name=job.name or job.id,
            trigger_type=trigger_type,
            trigger_info=trigger_info,
            next_run_time=next_run,
            is_paused=job.next_run_time is None
        )

    def pause_job(self, job_id: str) -> bool:
        """特定のジョブを一時停止"""
        if not self.scheduler:
            return False

        job = self.scheduler.get_job(job_id)
        if not job:
            return False

        self.scheduler.pause_job(job_id)
        logger.info(f"Job {job_id} paused")
        return True

    def resume_job(self, job_id: str) -> bool:
        """特定のジョブを再開"""
        if not self.scheduler:
            return False

        job = self.scheduler.get_job(job_id)
        if not job:
            return False

        self.scheduler.resume_job(job_id)
        logger.info(f"Job {job_id} resumed")
        return True

    async def trigger_job(self, job_id: str) -> bool:
        """特定のジョブを手動でトリガー"""
        if not self.scheduler:
            return False

        # ジョブIDに対応する関数を取得
        job_functions = {
            "ml_prediction_update": self._run_ml_prediction_update,
            "sentiment_analysis_morning": self._run_sentiment_analysis,
            "sentiment_analysis_afternoon": self._run_sentiment_analysis,
            "watchlist_alert_check": self._run_watchlist_alert_check,
            "market_data_cache_refresh": self._run_market_data_cache_refresh,
        }

        func = job_functions.get(job_id)
        if not func:
            logger.error(f"Unknown job ID: {job_id}")
            return False

        # 手動トリガーのログを記録
        self._running_jobs[job_id] = datetime.now(JST)

        try:
            await func()
            return True
        except Exception as e:
            logger.error(f"Manual trigger of job {job_id} failed: {e}")
            return False

    def get_logs(self, job_id: Optional[str] = None, limit: int = 50) -> List[JobLog]:
        """ジョブ実行ログを取得"""
        logs = self._job_logs

        if job_id:
            logs = [log for log in logs if log.job_id == job_id]

        return logs[:limit]

    def clear_logs(self):
        """ログをクリア"""
        self._job_logs.clear()
        logger.info("Job logs cleared")


# シングルトンインスタンス
scheduler_service = SchedulerService()
