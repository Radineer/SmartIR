"""
通知API
通知設定の管理とテスト通知の送信
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from enum import Enum

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.notification import NotificationSettings, NotificationLog, NotificationChannel
from app.services.notification_service import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


# ===============================
# スキーマ定義
# ===============================

class NotificationSettingsCreate(BaseModel):
    """通知設定作成スキーマ"""
    # メール通知設定
    email_enabled: bool = False
    email_address: Optional[EmailStr] = None
    email_provider: Optional[str] = "sendgrid"  # sendgrid or ses

    # Slack通知設定
    slack_enabled: bool = False
    slack_webhook_url: Optional[str] = None
    slack_channel: Optional[str] = None

    # 通知タイプごとの設定
    notify_price_above: bool = True
    notify_price_below: bool = True
    notify_volatility: bool = True
    notify_ir_release: bool = True

    # 通知頻度設定（分）
    notification_cooldown: int = 60

    class Config:
        json_schema_extra = {
            "example": {
                "email_enabled": True,
                "email_address": "user@example.com",
                "email_provider": "sendgrid",
                "slack_enabled": True,
                "slack_webhook_url": "https://hooks.slack.com/services/xxx/yyy/zzz",
                "slack_channel": "#alerts",
                "notify_price_above": True,
                "notify_price_below": True,
                "notify_volatility": True,
                "notify_ir_release": True,
                "notification_cooldown": 60
            }
        }


class NotificationSettingsResponse(BaseModel):
    """通知設定レスポンススキーマ"""
    id: int
    user_id: int

    email_enabled: bool
    email_address: Optional[str]
    email_provider: Optional[str]

    slack_enabled: bool
    slack_webhook_url: Optional[str]
    slack_channel: Optional[str]

    notify_price_above: bool
    notify_price_below: bool
    notify_volatility: bool
    notify_ir_release: bool

    notification_cooldown: int

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TestNotificationRequest(BaseModel):
    """テスト通知リクエストスキーマ"""
    channel: str  # email or slack

    class Config:
        json_schema_extra = {
            "example": {
                "channel": "email"
            }
        }


class TestNotificationResponse(BaseModel):
    """テスト通知レスポンススキーマ"""
    success: bool
    channel: str
    message: str


class NotificationLogResponse(BaseModel):
    """通知ログレスポンススキーマ"""
    id: int
    user_id: int
    alert_id: Optional[int]
    channel: str
    status: str
    subject: Optional[str]
    message: Optional[str]
    error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ===============================
# APIエンドポイント
# ===============================

@router.post("/settings", response_model=NotificationSettingsResponse)
async def save_notification_settings(
    settings_data: NotificationSettingsCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    通知設定を保存

    ユーザーの通知設定を作成または更新します。
    """
    # Slack Webhook URLの簡易バリデーション
    if settings_data.slack_enabled and settings_data.slack_webhook_url:
        if not settings_data.slack_webhook_url.startswith("https://hooks.slack.com/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Slack webhook URL format"
            )

    # メールアドレスが有効化されているが設定されていない場合
    if settings_data.email_enabled and not settings_data.email_address:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address is required when email notification is enabled"
        )

    settings = notification_service.create_or_update_settings(
        db=db,
        user_id=current_user.id,
        settings_data=settings_data.model_dump(exclude_unset=True)
    )

    return settings


@router.get("/settings", response_model=Optional[NotificationSettingsResponse])
async def get_notification_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    通知設定を取得

    現在のユーザーの通知設定を取得します。
    設定が存在しない場合はnullを返します。
    """
    settings = notification_service.get_settings(db, current_user.id)

    if not settings:
        # デフォルト設定を返す代わりにnullを返す
        return None

    return settings


@router.post("/test", response_model=TestNotificationResponse)
async def send_test_notification(
    request: TestNotificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    テスト通知を送信

    指定されたチャンネル（email または slack）にテスト通知を送信します。
    通知設定が有効化されている必要があります。
    """
    # チャンネルのバリデーション
    valid_channels = [NotificationChannel.EMAIL.value, NotificationChannel.SLACK.value]
    if request.channel not in valid_channels:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid channel. Must be one of: {', '.join(valid_channels)}"
        )

    # 通知設定を確認
    settings = notification_service.get_settings(db, current_user.id)
    if not settings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Notification settings not configured. Please save settings first."
        )

    # チャンネルごとの有効化チェック
    if request.channel == NotificationChannel.EMAIL.value:
        if not settings.email_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email notification is not enabled"
            )
        if not settings.email_address:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address is not configured"
            )
    elif request.channel == NotificationChannel.SLACK.value:
        if not settings.slack_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Slack notification is not enabled"
            )

    # テスト通知を送信
    success = await notification_service.send_test_notification(
        db=db,
        user_id=current_user.id,
        channel=request.channel
    )

    if success:
        return TestNotificationResponse(
            success=True,
            channel=request.channel,
            message=f"Test notification sent successfully via {request.channel}"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send test notification via {request.channel}"
        )


@router.get("/logs", response_model=List[NotificationLogResponse])
async def get_notification_logs(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    通知ログを取得

    ユーザーの通知送信履歴を取得します。
    """
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limit must be between 1 and 100"
        )

    logs = notification_service.get_notification_logs(
        db=db,
        user_id=current_user.id,
        limit=limit
    )

    return logs


@router.delete("/settings", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    通知設定を削除

    ユーザーの通知設定を完全に削除します。
    """
    settings = notification_service.get_settings(db, current_user.id)

    if not settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification settings not found"
        )

    db.delete(settings)
    db.commit()

    return None
