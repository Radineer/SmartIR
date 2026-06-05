"""TikTok Content Posting API client.

Uses the TikTok Content Posting API v2 for video uploads.
Lazy-loads httpx to keep it optional. Uses PostLog DB table
for deduplication and audit trail.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.post_log import PostLog, PostPlatform, PostType

log = logging.getLogger(__name__)

TIKTOK_API_BASE = "https://open.tiktokapis.com"


def _get_httpx():
    try:
        import httpx
        return httpx
    except ImportError:
        raise ImportError(
            "TikTok連携には httpx が必要です。\n"
            "pip install httpx でインストールしてください。"
        )


def _get_access_token() -> str:
    token = os.getenv("TIKTOK_ACCESS_TOKEN")
    if not token:
        raise ValueError("TIKTOK_ACCESS_TOKEN を環境変数に設定してください")
    return token


class TikTokClient:
    """TikTok動画投稿クライアント using Content Posting API."""

    def __init__(self):
        self._httpx = None

    @property
    def httpx(self):
        if self._httpx is None:
            self._httpx = _get_httpx()
        return self._httpx

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {_get_access_token()}",
            "Content-Type": "application/json; charset=UTF-8",
        }

    def _init_upload(self, video_size: int) -> tuple[str, str]:
        """Initialize video upload via inbox endpoint.

        Returns (publish_id, upload_url).
        """
        resp = self.httpx.post(
            f"{TIKTOK_API_BASE}/v2/post/publish/inbox/video/init/",
            headers=self._headers(),
            json={
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": video_size,
                    "chunk_size": video_size,
                    "total_chunk_count": 1,
                },
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("error", {}).get("code") != "ok":
            raise RuntimeError(f"TikTok init upload failed: {data}")

        publish_id = data["data"]["publish_id"]
        upload_url = data["data"]["upload_url"]
        return publish_id, upload_url

    def _upload_video(self, upload_url: str, video_path: str, video_size: int) -> None:
        """Upload video binary to the upload URL."""
        with open(video_path, "rb") as f:
            video_bytes = f.read()

        headers = {
            "Content-Type": "video/mp4",
            "Content-Length": str(video_size),
            "Content-Range": f"bytes 0-{video_size - 1}/{video_size}",
        }
        resp = self.httpx.put(
            upload_url,
            headers=headers,
            content=video_bytes,
            timeout=300,
        )
        resp.raise_for_status()
        log.info("TikTok video upload complete (%d bytes)", video_size)

    def _publish_video(
        self,
        title: str,
        description: str,
        hashtags: list[str] | None = None,
    ) -> str:
        """Publish the uploaded video.

        Returns publish_id for status tracking.
        """
        caption = title
        if description:
            caption = f"{title}\n{description}"
        if hashtags:
            tags_str = " ".join(f"#{t.lstrip('#')}" for t in hashtags)
            caption = f"{caption}\n{tags_str}"

        # Truncate to TikTok caption limit (2200 chars)
        caption = caption[:2200]

        resp = self.httpx.post(
            f"{TIKTOK_API_BASE}/v2/post/publish/video/init/",
            headers=self._headers(),
            json={
                "post_info": {
                    "title": caption,
                    "privacy_level": "PUBLIC_TO_EVERYONE",
                    "disable_duet": False,
                    "disable_comment": False,
                    "disable_stitch": False,
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": 0,  # Already uploaded via inbox
                },
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("error", {}).get("code") != "ok":
            raise RuntimeError(f"TikTok publish failed: {data}")

        return data["data"]["publish_id"]

    def check_publish_status(self, publish_id: str) -> dict:
        """Check the status of a published video.

        Returns dict with status and optional video URL.
        """
        resp = self.httpx.post(
            f"{TIKTOK_API_BASE}/v2/post/publish/status/fetch/",
            headers=self._headers(),
            json={"publish_id": publish_id},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("error", {}).get("code") != "ok":
            raise RuntimeError(f"TikTok status check failed: {data}")

        return data.get("data", {})

    def _wait_for_publish(
        self, publish_id: str, max_wait: int = 120, interval: int = 5
    ) -> dict:
        """Poll publish status until complete or timeout."""
        elapsed = 0
        while elapsed < max_wait:
            status_data = self.check_publish_status(publish_id)
            status = status_data.get("status", "UNKNOWN")

            if status == "PUBLISH_COMPLETE":
                log.info("TikTok video published successfully (publish_id=%s)", publish_id)
                return status_data
            elif status in ("FAILED", "PUBLISH_FAILED"):
                raise RuntimeError(
                    f"TikTok publish failed: {status_data.get('fail_reason', 'unknown')}"
                )

            log.debug("TikTok publish status: %s, waiting...", status)
            time.sleep(interval)
            elapsed += interval

        raise TimeoutError(
            f"TikTok publish did not complete within {max_wait}s (publish_id={publish_id})"
        )

    def post_video(
        self,
        db: Session,
        video_path: str,
        title: str,
        description: str = "",
        hashtags: list[str] | None = None,
        post_type: PostType = PostType.VIDEO,
        document_id: int | None = None,
        company_id: int | None = None,
        dry_run: bool = False,
    ) -> str | None:
        """Upload and publish a video to TikTok.

        Returns publish_id if posted, None if dry_run or duplicate.
        """
        # Check for duplicate
        if document_id is not None:
            existing = (
                db.query(PostLog)
                .filter(
                    PostLog.platform == PostPlatform.TIKTOK,
                    PostLog.post_type == post_type,
                    PostLog.document_id == document_id,
                )
                .first()
            )
            if existing:
                log.info(
                    "TikTok video already posted for document_id=%s, type=%s",
                    document_id,
                    post_type,
                )
                return None

        if dry_run:
            log.info("[DRY-RUN] Would post TikTok video: %s", title)
            return None

        path = Path(video_path)
        if not path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        video_size = path.stat().st_size
        log.info("Uploading video to TikTok (%d bytes): %s", video_size, title)

        # Step 1: Initialize upload
        publish_id, upload_url = self._init_upload(video_size)

        # Step 2: Upload video binary
        self._upload_video(upload_url, video_path, video_size)

        # Step 3: Publish
        publish_id = self._publish_video(title, description, hashtags)

        # Step 4: Wait for publish to complete
        try:
            status_data = self._wait_for_publish(publish_id)
        except (TimeoutError, RuntimeError) as e:
            log.warning("TikTok publish may still be processing: %s", e)

        # Log to DB
        post_log = PostLog(
            platform=PostPlatform.TIKTOK,
            post_type=post_type,
            external_id=publish_id,
            document_id=document_id,
            company_id=company_id,
            content_preview=f"{title} - {description}"[:200],
            metadata_={"hashtags": hashtags or []},
        )
        db.add(post_log)
        db.commit()

        log.info("TikTok video posted: %s (publish_id=%s)", post_type.value, publish_id)
        return publish_id
