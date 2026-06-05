"""
配信ジョブモデル
動画配信の実行履歴と結果を保存
"""

from sqlalchemy import Column, String, Integer, Float, ForeignKey, JSON, Enum as SQLEnum, Text, DateTime
from sqlalchemy.orm import relationship
from enum import Enum
from app.models.base import BaseModel


class BroadcastStatus(str, Enum):
    """配信ジョブのステータス"""
    PENDING = "pending"          # スケジュール待ち
    SCHEDULED = "scheduled"      # スケジュール済み
    GENERATING = "generating"    # 動画生成中
    UPLOADING = "uploading"      # アップロード中
    COMPLETED = "completed"      # 完了
    FAILED = "failed"            # 失敗
    CANCELLED = "cancelled"      # キャンセル済み


class BroadcastJob(BaseModel):
    """配信ジョブモデル"""
    __tablename__ = "broadcast_jobs"

    # ユーザーとの紐付け
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # 対象IR文書
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True, index=True)

    # 配信設定
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    tags = Column(JSON, nullable=True)
    privacy_status = Column(String(20), default="unlisted")

    # スケジュール
    publish_time = Column(DateTime, nullable=True)

    # ファイルパス
    video_path = Column(String(512), nullable=True)
    thumbnail_path = Column(String(512), nullable=True)

    # 実行状態
    status = Column(
        SQLEnum(BroadcastStatus),
        default=BroadcastStatus.PENDING,
        nullable=False,
        index=True,
    )
    error_message = Column(Text, nullable=True)

    # アップロード結果
    video_id = Column(String(50), nullable=True)  # YouTube video ID
    video_url = Column(String(512), nullable=True)

    # 結果詳細（JSON）
    result = Column(JSON, nullable=True)

    # リレーション
    user = relationship("User", backref="broadcast_jobs")
    document = relationship("Document", backref="broadcast_jobs")

    def __repr__(self):
        return f"<BroadcastJob(id={self.id}, status={self.status}, title={self.title})>"
