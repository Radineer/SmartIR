"""
通知設定モデル
ユーザーごとの通知設定を管理
"""

from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from enum import Enum
from app.models.base import BaseModel


class NotificationChannel(str, Enum):
    """通知チャンネル"""
    EMAIL = "email"
    SLACK = "slack"


class NotificationSettings(BaseModel):
    """通知設定モデル"""
    __tablename__ = "notification_settings"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    # メール通知設定
    email_enabled = Column(Boolean, default=False, nullable=False)
    email_address = Column(String(255), nullable=True)
    email_provider = Column(String(50), default="sendgrid", nullable=True)  # sendgrid or ses

    # Slack通知設定
    slack_enabled = Column(Boolean, default=False, nullable=False)
    slack_webhook_url = Column(Text, nullable=True)
    slack_channel = Column(String(100), nullable=True)

    # 通知タイプごとの設定
    notify_price_above = Column(Boolean, default=True, nullable=False)
    notify_price_below = Column(Boolean, default=True, nullable=False)
    notify_volatility = Column(Boolean, default=True, nullable=False)
    notify_ir_release = Column(Boolean, default=True, nullable=False)

    # 通知頻度設定（分）- 同じアラートの再通知を抑制
    notification_cooldown = Column(Integer, default=60, nullable=False)

    # カスタム設定（JSON形式で拡張可能）
    custom_settings = Column(JSON, nullable=True)

    # リレーション
    user = relationship("User", backref="notification_settings")


class NotificationLog(BaseModel):
    """通知ログモデル"""
    __tablename__ = "notification_logs"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_id = Column(Integer, ForeignKey("price_alerts.id", ondelete="SET NULL"), nullable=True, index=True)

    channel = Column(String(50), nullable=False)  # email, slack
    status = Column(String(50), nullable=False)   # sent, failed, pending

    # 通知内容
    subject = Column(String(255), nullable=True)
    message = Column(Text, nullable=True)

    # エラー情報
    error_message = Column(Text, nullable=True)

    # 追加情報
    extra_data = Column(JSON, nullable=True)
