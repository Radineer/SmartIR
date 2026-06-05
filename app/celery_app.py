import os
from celery import Celery
from celery.schedules import crontab

# Redis URL
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Celeryアプリケーション
celery_app = Celery(
    "smartir",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "app.tasks.crawler_tasks",
        "app.tasks.analysis_tasks",
        "app.tasks.publish_tasks",
    ]
)

# Celery設定
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Tokyo",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10分
    worker_prefetch_multiplier=1,
    worker_concurrency=4,
)

# 定期実行スケジュール
celery_app.conf.beat_schedule = {
    # TDnet: 10分おき（営業時間内）
    "crawl-tdnet-every-10-minutes": {
        "task": "app.tasks.crawler_tasks.crawl_tdnet",
        "schedule": crontab(minute="*/10", hour="8-18", day_of_week="1-5"),
        "args": (1,),  # days=1
    },
    # EDINET: 1時間おき
    "crawl-edinet-every-hour": {
        "task": "app.tasks.crawler_tasks.crawl_edinet",
        "schedule": crontab(minute=0, hour="9-17", day_of_week="1-5"),
        "args": (1,),  # days=1
    },
    # 企業サイト: 毎日朝6時
    "crawl-company-sites-daily": {
        "task": "app.tasks.crawler_tasks.crawl_all_company_sites",
        "schedule": crontab(minute=0, hour=6),
    },
    # 未処理ドキュメントの分析: 30分おき
    "analyze-unprocessed-documents": {
        "task": "app.tasks.analysis_tasks.analyze_unprocessed_documents",
        "schedule": crontab(minute="*/30"),
        "args": (10,),  # batch_size=10
    },
    # 日次まとめ (note + X): 毎日20:00 JST
    "publish-daily-summary": {
        "task": "app.tasks.publish_tasks.publish_daily_summary",
        "schedule": crontab(hour=20, minute=0),
    },
    # 週次まとめ (X): 毎週日曜10:00 JST
    "publish-weekly-summary": {
        "task": "app.tasks.publish_tasks.publish_weekly_summary",
        "schedule": crontab(hour=10, minute=0, day_of_week=0),
    },
}
