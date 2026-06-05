"""
YouTube Live API サービス

liveBroadcasts / liveStreams API を使って配信イベントの作成・開始・終了を管理。
OAuth パターンは youtube_uploader.py を流用。
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


class YouTubeLiveService:
    """YouTube Live 配信を管理するクラス"""

    def __init__(self):
        self.credentials = None
        self.youtube = None

    # ------------------------------------------------------------------
    # 認証
    # ------------------------------------------------------------------

    def authenticate(self, credentials_path: str = "client_secrets.json"):
        """インタラクティブ OAuth 認証"""
        flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
        self.credentials = flow.run_local_server(port=8080)
        self.youtube = build("youtube", "v3", credentials=self.credentials)
        logger.info("YouTube Live authentication successful")
        return self

    def authenticate_with_tokens(self, token_path: str = "youtube_tokens.json"):
        """保存済みトークンで認証。トークンが期限切れなら自動リフレッシュ"""
        path = Path(token_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Token file not found: {token_path}. "
                "Run authenticate() first to generate tokens."
            )

        try:
            with open(path, "r") as f:
                token_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {token_path}: {e}")

        if "token" not in token_data:
            raise ValueError(f"Missing 'token' key in {token_path}")

        self.credentials = Credentials(
            token=token_data["token"],
            refresh_token=token_data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("YOUTUBE_CLIENT_ID"),
            client_secret=os.getenv("YOUTUBE_CLIENT_SECRET"),
            scopes=SCOPES,
        )

        # トークンが期限切れならリフレッシュ
        if self.credentials.expired and self.credentials.refresh_token:
            logger.info("Token expired, refreshing...")
            self.credentials.refresh(Request())
            self.save_credentials(token_path)
            logger.info("Token refreshed and saved")

        self._token_path = token_path
        self.youtube = build("youtube", "v3", credentials=self.credentials)
        logger.info("YouTube Live token authentication successful")
        return self

    def save_credentials(self, token_path: str = "youtube_tokens.json"):
        """認証情報を保存"""
        if self.credentials:
            token_data = {
                "token": self.credentials.token,
                "refresh_token": self.credentials.refresh_token,
            }
            with open(token_path, "w") as f:
                json.dump(token_data, f)
            logger.info(f"Credentials saved to {token_path}")

    def _ensure_authenticated(self):
        if not self.youtube:
            raise RuntimeError("YouTube API not authenticated. Call authenticate() first.")
        # 自動リフレッシュ（長時間配信対応）
        if self.credentials and self.credentials.expired and self.credentials.refresh_token:
            logger.info("Token expired during session, refreshing...")
            self.credentials.refresh(Request())
            token_path = getattr(self, "_token_path", "youtube_tokens.json")
            self.save_credentials(token_path)

    def _api_call_with_retry(self, api_fn, max_retries: int = 3):
        """YouTube API 呼び出しをリトライ付きで実行（429/5xx対応）"""
        for attempt in range(max_retries):
            try:
                return api_fn()
            except HttpError as e:
                status = e.resp.status
                if status == 429 or status >= 500:
                    wait = min(2 ** attempt * 5, 60)
                    logger.warning(f"YouTube API error {status}, retry in {wait}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait)
                    # 401の場合はトークンリフレッシュ試行
                elif status == 401 and self.credentials and self.credentials.refresh_token:
                    logger.warning("Got 401, attempting token refresh...")
                    self.credentials.refresh(Request())
                    token_path = getattr(self, "_token_path", "youtube_tokens.json")
                    self.save_credentials(token_path)
                    self.youtube = build("youtube", "v3", credentials=self.credentials)
                else:
                    raise
        # 最後の試行
        return api_fn()

    # ------------------------------------------------------------------
    # 配信イベント管理
    # ------------------------------------------------------------------

    def create_broadcast(
        self,
        title: str,
        description: str = "",
        scheduled_start: datetime | None = None,
        privacy_status: str = "unlisted",
        tags: list[str] | None = None,
    ) -> dict:
        """
        配信イベント（Broadcast）を作成

        Returns:
            dict: {"broadcast_id": str, "title": str, "scheduled_start": str}
        """
        self._ensure_authenticated()

        if scheduled_start is None:
            scheduled_start = datetime.now(JST) + timedelta(minutes=2)

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "scheduledStartTime": scheduled_start.isoformat(),
                "tags": tags or ["IR分析", "イリス", "AIVTuber"],
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            },
            "contentDetails": {
                "enableAutoStart": False,
                "enableAutoStop": False,
                "enableDvr": True,
                "enableEmbed": True,
                "recordFromStart": True,
            },
        }

        response = self._api_call_with_retry(
            lambda: self.youtube.liveBroadcasts().insert(
                part="snippet,status,contentDetails",
                body=body,
            ).execute()
        )

        broadcast_id = response["id"]
        logger.info(f"Broadcast created: {broadcast_id} ({title})")

        return {
            "broadcast_id": broadcast_id,
            "title": title,
            "scheduled_start": scheduled_start.isoformat(),
            "watch_url": f"https://www.youtube.com/watch?v={broadcast_id}",
        }

    def create_stream(self, title: str = "Iris Stream") -> dict:
        """
        ストリーム（RTMP エンドポイント）を作成

        Returns:
            dict: {"stream_id": str, "rtmp_url": str, "stream_key": str}
        """
        self._ensure_authenticated()

        body = {
            "snippet": {
                "title": title,
            },
            "cdn": {
                "frameRate": "30fps",
                "ingestionType": "rtmp",
                "resolution": "1080p",
            },
        }

        response = self._api_call_with_retry(
            lambda: self.youtube.liveStreams().insert(
                part="snippet,cdn",
                body=body,
            ).execute()
        )

        stream_id = response["id"]
        ingestion = response["cdn"]["ingestionInfo"]

        logger.info(f"Stream created: {stream_id}")

        return {
            "stream_id": stream_id,
            "rtmp_url": ingestion["ingestionAddress"],
            "stream_key": ingestion["streamName"],
        }

    def bind_broadcast_to_stream(self, broadcast_id: str, stream_id: str) -> dict:
        """Broadcast と Stream をバインド"""
        self._ensure_authenticated()

        response = self._api_call_with_retry(
            lambda: self.youtube.liveBroadcasts().bind(
                id=broadcast_id,
                part="id,contentDetails",
                streamId=stream_id,
            ).execute()
        )

        logger.info(f"Bound broadcast {broadcast_id} to stream {stream_id}")
        return response

    def transition_broadcast(self, broadcast_id: str, status: str) -> dict:
        """
        Broadcast のステータスを遷移

        Args:
            broadcast_id: ブロードキャストID
            status: "testing" | "live" | "complete"
        """
        self._ensure_authenticated()

        response = self._api_call_with_retry(
            lambda: self.youtube.liveBroadcasts().transition(
                broadcastStatus=status,
                id=broadcast_id,
                part="id,status",
            ).execute()
        )

        logger.info(f"Broadcast {broadcast_id} transitioned to: {status}")
        return response

    def start_broadcast(self, broadcast_id: str) -> dict:
        """配信を開始"""
        return self.transition_broadcast(broadcast_id, "live")

    def end_broadcast(self, broadcast_id: str) -> dict:
        """配信を終了"""
        return self.transition_broadcast(broadcast_id, "complete")

    # ------------------------------------------------------------------
    # エンドツーエンド ヘルパー
    # ------------------------------------------------------------------

    def setup_live_event(
        self,
        title: str,
        description: str = "",
        privacy_status: str = "unlisted",
        tags: list[str] | None = None,
    ) -> dict:
        """
        配信イベントを一括セットアップ（broadcast + stream + bind）

        Returns:
            dict: {
                "broadcast_id": str,
                "stream_id": str,
                "rtmp_url": str,
                "stream_key": str,
                "watch_url": str,
            }
        """
        broadcast = self.create_broadcast(
            title=title,
            description=description,
            privacy_status=privacy_status,
            tags=tags,
        )

        stream = self.create_stream(title=f"{title} - Stream")

        self.bind_broadcast_to_stream(broadcast["broadcast_id"], stream["stream_id"])

        return {
            "broadcast_id": broadcast["broadcast_id"],
            "stream_id": stream["stream_id"],
            "rtmp_url": stream["rtmp_url"],
            "stream_key": stream["stream_key"],
            "watch_url": broadcast["watch_url"],
        }

    def get_live_chat_id(self, broadcast_id: str) -> str | None:
        """配信のライブチャットIDを取得"""
        self._ensure_authenticated()

        response = self._api_call_with_retry(
            lambda: self.youtube.liveBroadcasts().list(
                id=broadcast_id,
                part="snippet",
            ).execute()
        )

        items = response.get("items", [])
        if items:
            return items[0]["snippet"].get("liveChatId")
        return None
