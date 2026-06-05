"""
通知サービス
メール通知とSlack通知を提供
"""

import os
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from abc import ABC, abstractmethod
import httpx
from sqlalchemy.orm import Session

from app.models.notification import NotificationSettings, NotificationLog, NotificationChannel
from app.models.watchlist import AlertType

logger = logging.getLogger(__name__)


class NotificationProvider(ABC):
    """通知プロバイダーの抽象基底クラス"""

    @abstractmethod
    async def send(
        self,
        recipient: str,
        subject: str,
        message: str,
        **kwargs
    ) -> bool:
        """通知を送信"""
        pass


class SendGridProvider(NotificationProvider):
    """SendGridメール通知プロバイダー"""

    def __init__(self):
        self.api_key = os.getenv("SENDGRID_API_KEY")
        self.from_email = os.getenv("SENDGRID_FROM_EMAIL", "noreply@smartir.jp")
        self.api_url = "https://api.sendgrid.com/v3/mail/send"

    async def send(
        self,
        recipient: str,
        subject: str,
        message: str,
        **kwargs
    ) -> bool:
        """
        SendGridでメールを送信

        Args:
            recipient: 送信先メールアドレス
            subject: 件名
            message: 本文

        Returns:
            送信成功したかどうか
        """
        if not self.api_key:
            logger.error("SendGrid API key is not configured")
            return False

        html_content = kwargs.get("html_content", f"<p>{message}</p>")

        payload = {
            "personalizations": [
                {
                    "to": [{"email": recipient}],
                    "subject": subject
                }
            ],
            "from": {"email": self.from_email},
            "content": [
                {"type": "text/plain", "value": message},
                {"type": "text/html", "value": html_content}
            ]
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=30.0
                )
                if response.status_code in (200, 201, 202):
                    logger.info(f"SendGrid email sent successfully to {recipient}")
                    return True
                else:
                    logger.error(f"SendGrid API error: {response.status_code} - {response.text}")
                    return False
        except Exception as e:
            logger.error(f"SendGrid send error: {e}")
            return False


class AWSSESProvider(NotificationProvider):
    """AWS SESメール通知プロバイダー"""

    def __init__(self):
        self.region = os.getenv("AWS_DEFAULT_REGION", "ap-northeast-1")
        self.from_email = os.getenv("SES_FROM_EMAIL", "noreply@smartir.jp")

    async def send(
        self,
        recipient: str,
        subject: str,
        message: str,
        **kwargs
    ) -> bool:
        """
        AWS SESでメールを送信

        Args:
            recipient: 送信先メールアドレス
            subject: 件名
            message: 本文

        Returns:
            送信成功したかどうか
        """
        try:
            import boto3
            from botocore.exceptions import ClientError

            client = boto3.client("ses", region_name=self.region)

            html_content = kwargs.get("html_content", f"<p>{message}</p>")

            response = client.send_email(
                Source=self.from_email,
                Destination={
                    "ToAddresses": [recipient]
                },
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Text": {"Data": message, "Charset": "UTF-8"},
                        "Html": {"Data": html_content, "Charset": "UTF-8"}
                    }
                }
            )
            logger.info(f"AWS SES email sent successfully: {response['MessageId']}")
            return True
        except ImportError:
            logger.error("boto3 is not installed for AWS SES")
            return False
        except ClientError as e:
            logger.error(f"AWS SES error: {e.response['Error']['Message']}")
            return False
        except Exception as e:
            logger.error(f"AWS SES send error: {e}")
            return False


class SlackProvider(NotificationProvider):
    """Slack Webhook通知プロバイダー"""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")

    async def send(
        self,
        recipient: str,  # Slackの場合はチャンネル名として使用
        subject: str,
        message: str,
        **kwargs
    ) -> bool:
        """
        Slack Webhookで通知を送信

        Args:
            recipient: チャンネル名（オプション）
            subject: 件名（Slackではタイトルとして使用）
            message: 本文

        Returns:
            送信成功したかどうか
        """
        webhook_url = kwargs.get("webhook_url", self.webhook_url)
        if not webhook_url:
            logger.error("Slack webhook URL is not configured")
            return False

        # Slack Block Kitフォーマット
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": subject,
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message
                }
            }
        ]

        # アラート詳細がある場合は追加
        alert_details = kwargs.get("alert_details")
        if alert_details:
            fields = []
            for key, value in alert_details.items():
                fields.append({
                    "type": "mrkdwn",
                    "text": f"*{key}:*\n{value}"
                })
            if fields:
                blocks.append({
                    "type": "section",
                    "fields": fields[:10]  # Slackの制限
                })

        # タイムスタンプを追加
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                }
            ]
        })

        payload = {
            "blocks": blocks,
            "text": f"{subject}: {message}"  # フォールバックテキスト
        }

        if recipient and recipient.startswith("#"):
            payload["channel"] = recipient

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    timeout=30.0
                )
                if response.status_code == 200:
                    logger.info(f"Slack notification sent successfully")
                    return True
                else:
                    logger.error(f"Slack webhook error: {response.status_code} - {response.text}")
                    return False
        except Exception as e:
            logger.error(f"Slack send error: {e}")
            return False


class NotificationService:
    """通知サービスクラス"""

    def __init__(self):
        self.email_providers = {
            "sendgrid": SendGridProvider(),
            "ses": AWSSESProvider()
        }
        self.slack_provider = SlackProvider()

    def get_settings(self, db: Session, user_id: int) -> Optional[NotificationSettings]:
        """
        ユーザーの通知設定を取得

        Args:
            db: DBセッション
            user_id: ユーザーID

        Returns:
            通知設定またはNone
        """
        return db.query(NotificationSettings).filter(
            NotificationSettings.user_id == user_id
        ).first()

    def create_or_update_settings(
        self,
        db: Session,
        user_id: int,
        settings_data: Dict[str, Any]
    ) -> NotificationSettings:
        """
        通知設定を作成または更新

        Args:
            db: DBセッション
            user_id: ユーザーID
            settings_data: 設定データ

        Returns:
            通知設定
        """
        settings = self.get_settings(db, user_id)

        if settings:
            # 既存の設定を更新
            for key, value in settings_data.items():
                if hasattr(settings, key) and key != "user_id":
                    setattr(settings, key, value)
        else:
            # 新規作成
            settings = NotificationSettings(
                user_id=user_id,
                **settings_data
            )
            db.add(settings)

        db.commit()
        db.refresh(settings)
        return settings

    async def send_email_notification(
        self,
        db: Session,
        user_id: int,
        subject: str,
        message: str,
        alert_id: Optional[int] = None,
        html_content: Optional[str] = None
    ) -> bool:
        """
        メール通知を送信

        Args:
            db: DBセッション
            user_id: ユーザーID
            subject: 件名
            message: 本文
            alert_id: アラートID（オプション）
            html_content: HTML本文（オプション）

        Returns:
            送信成功したかどうか
        """
        settings = self.get_settings(db, user_id)

        if not settings or not settings.email_enabled or not settings.email_address:
            logger.warning(f"Email notification not enabled for user {user_id}")
            return False

        provider_name = settings.email_provider or "sendgrid"
        provider = self.email_providers.get(provider_name)

        if not provider:
            logger.error(f"Unknown email provider: {provider_name}")
            return False

        success = await provider.send(
            recipient=settings.email_address,
            subject=subject,
            message=message,
            html_content=html_content
        )

        # 通知ログを保存
        self._log_notification(
            db=db,
            user_id=user_id,
            alert_id=alert_id,
            channel=NotificationChannel.EMAIL.value,
            status="sent" if success else "failed",
            subject=subject,
            message=message,
            error_message=None if success else "Failed to send email"
        )

        return success

    async def send_slack_notification(
        self,
        db: Session,
        user_id: int,
        subject: str,
        message: str,
        alert_id: Optional[int] = None,
        alert_details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Slack通知を送信

        Args:
            db: DBセッション
            user_id: ユーザーID
            subject: タイトル
            message: 本文
            alert_id: アラートID（オプション）
            alert_details: アラート詳細（オプション）

        Returns:
            送信成功したかどうか
        """
        settings = self.get_settings(db, user_id)

        if not settings or not settings.slack_enabled:
            logger.warning(f"Slack notification not enabled for user {user_id}")
            return False

        webhook_url = settings.slack_webhook_url or os.getenv("SLACK_WEBHOOK_URL")
        if not webhook_url:
            logger.error("Slack webhook URL not configured")
            return False

        slack_provider = SlackProvider(webhook_url)
        success = await slack_provider.send(
            recipient=settings.slack_channel or "",
            subject=subject,
            message=message,
            alert_details=alert_details
        )

        # 通知ログを保存
        self._log_notification(
            db=db,
            user_id=user_id,
            alert_id=alert_id,
            channel=NotificationChannel.SLACK.value,
            status="sent" if success else "failed",
            subject=subject,
            message=message,
            error_message=None if success else "Failed to send Slack notification"
        )

        return success

    async def send_alert_notification(
        self,
        db: Session,
        user_id: int,
        alert_id: int,
        ticker_code: str,
        stock_name: str,
        alert_type: AlertType,
        threshold: float,
        current_price: float
    ) -> Dict[str, bool]:
        """
        アラートトリガー時の通知を送信

        Args:
            db: DBセッション
            user_id: ユーザーID
            alert_id: アラートID
            ticker_code: ティッカーコード
            stock_name: 銘柄名
            alert_type: アラートタイプ
            threshold: 閾値
            current_price: 現在価格

        Returns:
            各チャンネルの送信結果
        """
        settings = self.get_settings(db, user_id)
        if not settings:
            return {"email": False, "slack": False}

        # アラートタイプに応じた通知可否をチェック
        should_notify = self._should_notify_alert_type(settings, alert_type)
        if not should_notify:
            logger.info(f"Notification disabled for alert type {alert_type}")
            return {"email": False, "slack": False}

        # 通知メッセージを作成
        subject, message, html_content = self._create_alert_message(
            ticker_code=ticker_code,
            stock_name=stock_name,
            alert_type=alert_type,
            threshold=threshold,
            current_price=current_price
        )

        results = {"email": False, "slack": False}

        # メール通知
        if settings.email_enabled:
            results["email"] = await self.send_email_notification(
                db=db,
                user_id=user_id,
                subject=subject,
                message=message,
                alert_id=alert_id,
                html_content=html_content
            )

        # Slack通知
        if settings.slack_enabled:
            alert_details = {
                "銘柄コード": ticker_code,
                "銘柄名": stock_name or "-",
                "アラートタイプ": self._get_alert_type_label(alert_type),
                "閾値": f"¥{threshold:,.0f}",
                "現在価格": f"¥{current_price:,.0f}"
            }
            results["slack"] = await self.send_slack_notification(
                db=db,
                user_id=user_id,
                subject=subject,
                message=message,
                alert_id=alert_id,
                alert_details=alert_details
            )

        return results

    async def send_test_notification(
        self,
        db: Session,
        user_id: int,
        channel: str
    ) -> bool:
        """
        テスト通知を送信

        Args:
            db: DBセッション
            user_id: ユーザーID
            channel: 通知チャンネル（email or slack）

        Returns:
            送信成功したかどうか
        """
        subject = "【SmartIR】テスト通知"
        message = "これはSmartIRからのテスト通知です。通知設定が正常に機能しています。"

        if channel == NotificationChannel.EMAIL.value:
            html_content = """
            <div style="font-family: 'Hiragino Sans', sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #1a73e8;">SmartIR テスト通知</h2>
                <p>これはSmartIRからのテスト通知です。</p>
                <p>通知設定が正常に機能しています。</p>
                <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 20px 0;">
                <p style="color: #666; font-size: 12px;">
                    このメールはSmartIRから自動送信されています。
                </p>
            </div>
            """
            return await self.send_email_notification(
                db=db,
                user_id=user_id,
                subject=subject,
                message=message,
                html_content=html_content
            )
        elif channel == NotificationChannel.SLACK.value:
            return await self.send_slack_notification(
                db=db,
                user_id=user_id,
                subject=subject,
                message=message
            )
        else:
            logger.error(f"Unknown notification channel: {channel}")
            return False

    def get_notification_logs(
        self,
        db: Session,
        user_id: int,
        limit: int = 50
    ) -> List[NotificationLog]:
        """
        通知ログを取得

        Args:
            db: DBセッション
            user_id: ユーザーID
            limit: 取得件数上限

        Returns:
            通知ログ一覧
        """
        return db.query(NotificationLog).filter(
            NotificationLog.user_id == user_id
        ).order_by(
            NotificationLog.created_at.desc()
        ).limit(limit).all()

    def _log_notification(
        self,
        db: Session,
        user_id: int,
        alert_id: Optional[int],
        channel: str,
        status: str,
        subject: Optional[str],
        message: Optional[str],
        error_message: Optional[str] = None
    ) -> NotificationLog:
        """通知ログを保存"""
        log = NotificationLog(
            user_id=user_id,
            alert_id=alert_id,
            channel=channel,
            status=status,
            subject=subject,
            message=message,
            error_message=error_message
        )
        db.add(log)
        db.commit()
        return log

    def _should_notify_alert_type(
        self,
        settings: NotificationSettings,
        alert_type: AlertType
    ) -> bool:
        """アラートタイプに応じた通知可否をチェック"""
        mapping = {
            AlertType.PRICE_ABOVE: settings.notify_price_above,
            AlertType.PRICE_BELOW: settings.notify_price_below,
            AlertType.VOLATILITY: settings.notify_volatility,
            AlertType.IR_RELEASE: settings.notify_ir_release,
        }
        return mapping.get(alert_type, True)

    def _get_alert_type_label(self, alert_type: AlertType) -> str:
        """アラートタイプのラベルを取得"""
        labels = {
            AlertType.PRICE_ABOVE: "価格上昇",
            AlertType.PRICE_BELOW: "価格下落",
            AlertType.VOLATILITY: "ボラティリティ",
            AlertType.IR_RELEASE: "IR資料公開",
        }
        return labels.get(alert_type, str(alert_type))

    def _create_alert_message(
        self,
        ticker_code: str,
        stock_name: str,
        alert_type: AlertType,
        threshold: float,
        current_price: float
    ) -> tuple:
        """アラート通知メッセージを作成"""
        alert_label = self._get_alert_type_label(alert_type)
        stock_display = f"{stock_name}（{ticker_code}）" if stock_name else ticker_code

        subject = f"【SmartIR アラート】{stock_display} - {alert_label}"

        message = f"""
{stock_display}のアラートがトリガーされました。

アラートタイプ: {alert_label}
閾値: ¥{threshold:,.0f}
現在価格: ¥{current_price:,.0f}

SmartIRでウォッチリストを確認してください。
"""

        html_content = f"""
        <div style="font-family: 'Hiragino Sans', sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #d93025;">🔔 SmartIR アラート</h2>
            <p><strong>{stock_display}</strong>のアラートがトリガーされました。</p>

            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <tr style="background-color: #f5f5f5;">
                    <td style="padding: 10px; border: 1px solid #ddd;">アラートタイプ</td>
                    <td style="padding: 10px; border: 1px solid #ddd;"><strong>{alert_label}</strong></td>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #ddd;">閾値</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">¥{threshold:,.0f}</td>
                </tr>
                <tr style="background-color: #f5f5f5;">
                    <td style="padding: 10px; border: 1px solid #ddd;">現在価格</td>
                    <td style="padding: 10px; border: 1px solid #ddd;"><strong>¥{current_price:,.0f}</strong></td>
                </tr>
            </table>

            <p>
                <a href="https://smartir.jp/watchlist"
                   style="background-color: #1a73e8; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px;">
                    ウォッチリストを確認
                </a>
            </p>

            <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 20px 0;">
            <p style="color: #666; font-size: 12px;">
                このメールはSmartIRから自動送信されています。<br>
                通知設定は <a href="https://smartir.jp/settings/notifications">こちら</a> から変更できます。
            </p>
        </div>
        """

        return subject, message.strip(), html_content


# シングルトンインスタンス
notification_service = NotificationService()
