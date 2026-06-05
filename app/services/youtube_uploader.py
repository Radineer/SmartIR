import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import json
import logging

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

class YouTubeUploader:
    """YouTube動画アップロードを管理するクラス"""

    def __init__(self):
        self.credentials = None
        self.youtube = None

    def authenticate(self, credentials_path: str = "client_secrets.json"):
        """
        OAuth認証を実行

        Args:
            credentials_path: クライアントシークレットファイルのパス

        Returns:
            self: メソッドチェーン用
        """
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path, SCOPES
            )
            self.credentials = flow.run_local_server(port=8080)
            self.youtube = build("youtube", "v3", credentials=self.credentials)
            logger.info("YouTube authentication successful")
            return self
        except Exception as e:
            logger.error(f"YouTube authentication failed: {str(e)}")
            raise

    def authenticate_with_tokens(self, token_path: str = "youtube_tokens.json"):
        """
        保存済みトークンで認証

        Args:
            token_path: トークンファイルのパス

        Returns:
            self: メソッドチェーン用
        """
        try:
            with open(token_path, "r") as f:
                token_data = json.load(f)

            self.credentials = Credentials(
                token=token_data["token"],
                refresh_token=token_data.get("refresh_token"),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=os.getenv("YOUTUBE_CLIENT_ID"),
                client_secret=os.getenv("YOUTUBE_CLIENT_SECRET"),
            )
            self.youtube = build("youtube", "v3", credentials=self.credentials)
            logger.info("YouTube authentication with tokens successful")
            return self
        except Exception as e:
            logger.error(f"Token authentication failed: {str(e)}")
            raise

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

    def upload_video(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: list[str] = None,
        category_id: str = "22",  # People & Blogs
        privacy_status: str = "unlisted",
    ) -> dict:
        """
        動画をYouTubeにアップロード

        Args:
            video_path: 動画ファイルのパス
            title: 動画タイトル
            description: 動画の説明
            tags: タグのリスト
            category_id: YouTubeカテゴリID (22=People & Blogs)
            privacy_status: 公開ステータス (public/private/unlisted)

        Returns:
            dict: アップロード結果（video_id, url）
        """
        if not self.youtube:
            raise RuntimeError("YouTube API not authenticated. Call authenticate() first.")

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags or ["IR分析", "決算", "イリス", "株式投資", "企業分析"],
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(
            video_path,
            chunksize=1024 * 1024,
            resumable=True,
            mimetype="video/mp4",
        )

        try:
            request = self.youtube.videos().insert(
                part=",".join(body.keys()),
                body=body,
                media_body=media,
            )

            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    logger.info(f"Upload progress: {int(status.progress() * 100)}%")

            video_id = response["id"]
            logger.info(f"Video uploaded successfully: {video_id}")

            return {
                "video_id": video_id,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "title": title,
            }
        except Exception as e:
            logger.error(f"Video upload failed: {str(e)}")
            raise

    def set_thumbnail(self, video_id: str, thumbnail_path: str) -> bool:
        """
        サムネイルを設定

        Args:
            video_id: YouTube動画ID
            thumbnail_path: サムネイル画像のパス

        Returns:
            bool: 成功したかどうか
        """
        if not self.youtube:
            raise RuntimeError("YouTube API not authenticated. Call authenticate() first.")

        try:
            media = MediaFileUpload(thumbnail_path, mimetype="image/png")
            self.youtube.thumbnails().set(
                videoId=video_id,
                media_body=media,
            ).execute()
            logger.info(f"Thumbnail set for video: {video_id}")
            return True
        except Exception as e:
            logger.error(f"Thumbnail upload failed: {str(e)}")
            return False

    def update_video(
        self,
        video_id: str,
        title: str = None,
        description: str = None,
        tags: list[str] = None,
        privacy_status: str = None,
    ) -> dict:
        """
        動画情報を更新

        Args:
            video_id: YouTube動画ID
            title: 新しいタイトル
            description: 新しい説明
            tags: 新しいタグリスト
            privacy_status: 新しい公開ステータス

        Returns:
            dict: 更新結果
        """
        if not self.youtube:
            raise RuntimeError("YouTube API not authenticated. Call authenticate() first.")

        # 現在の動画情報を取得
        video_response = self.youtube.videos().list(
            part="snippet,status",
            id=video_id
        ).execute()

        if not video_response.get("items"):
            raise ValueError(f"Video not found: {video_id}")

        video = video_response["items"][0]
        snippet = video["snippet"]
        status = video["status"]

        # 更新する項目を設定
        if title:
            snippet["title"] = title
        if description:
            snippet["description"] = description
        if tags:
            snippet["tags"] = tags
        if privacy_status:
            status["privacyStatus"] = privacy_status

        update_response = self.youtube.videos().update(
            part="snippet,status",
            body={
                "id": video_id,
                "snippet": snippet,
                "status": status,
            }
        ).execute()

        logger.info(f"Video updated: {video_id}")
        return {
            "video_id": video_id,
            "title": update_response["snippet"]["title"],
            "privacy_status": update_response["status"]["privacyStatus"],
        }

    def delete_video(self, video_id: str) -> bool:
        """
        動画を削除

        Args:
            video_id: YouTube動画ID

        Returns:
            bool: 成功したかどうか
        """
        if not self.youtube:
            raise RuntimeError("YouTube API not authenticated. Call authenticate() first.")

        try:
            self.youtube.videos().delete(id=video_id).execute()
            logger.info(f"Video deleted: {video_id}")
            return True
        except Exception as e:
            logger.error(f"Video deletion failed: {str(e)}")
            return False
