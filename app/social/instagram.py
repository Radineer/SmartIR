"""Instagram Graph API client for Reels posting.

Uses the Instagram Graph API to upload and publish Reels.
Lazy-loads httpx to keep it optional. Uses PostLog DB table
for deduplication and audit trail.
"""

from __future__ import annotations

import logging
import os
import time

from sqlalchemy.orm import Session

from app.models.post_log import PostLog, PostPlatform, PostType

log = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


def _get_httpx():
    try:
        import httpx
        return httpx
    except ImportError:
        raise ImportError(
            "Instagram連携には httpx が必要です。\n"
            "pip install httpx でインストールしてください。"
        )


def _get_credentials() -> tuple[str, str]:
    """Return (access_token, user_id)."""
    access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    user_id = os.getenv("INSTAGRAM_USER_ID")

    if not access_token or not user_id:
        raise ValueError(
            "INSTAGRAM_ACCESS_TOKEN, INSTAGRAM_USER_ID を環境変数に設定してください"
        )
    return access_token, user_id


class InstagramClient:
    """Instagram Reels投稿クライアント using Graph API."""

    def __init__(self):
        self._httpx = None

    @property
    def httpx(self):
        if self._httpx is None:
            self._httpx = _get_httpx()
        return self._httpx

    def _create_media_container(
        self,
        video_url: str,
        caption: str,
        access_token: str,
        user_id: str,
    ) -> str:
        """Create a media container for the Reel.

        The video_url must be a publicly accessible URL.
        Returns creation_id (container ID).
        """
        resp = self.httpx.post(
            f"{GRAPH_API_BASE}/{user_id}/media",
            params={
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption,
                "access_token": access_token,
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()

        if "id" not in data:
            raise RuntimeError(f"Instagram media container creation failed: {data}")

        creation_id = data["id"]
        log.info("Instagram media container created: %s", creation_id)
        return creation_id

    def _check_container_status(
        self,
        creation_id: str,
        access_token: str,
    ) -> str:
        """Check the status of a media container.

        Returns status_code: EXPIRED, ERROR, FINISHED, IN_PROGRESS, PUBLISHED.
        """
        resp = self.httpx.get(
            f"{GRAPH_API_BASE}/{creation_id}",
            params={
                "fields": "status_code",
                "access_token": access_token,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("status_code", "UNKNOWN")

    def _wait_for_container(
        self,
        creation_id: str,
        access_token: str,
        max_wait: int = 300,
        interval: int = 10,
    ) -> None:
        """Poll container status until FINISHED or timeout."""
        elapsed = 0
        while elapsed < max_wait:
            status = self._check_container_status(creation_id, access_token)

            if status == "FINISHED":
                log.info("Instagram container ready: %s", creation_id)
                return
            elif status in ("ERROR", "EXPIRED"):
                raise RuntimeError(
                    f"Instagram container failed with status: {status} "
                    f"(creation_id={creation_id})"
                )

            log.debug("Instagram container status: %s, waiting...", status)
            time.sleep(interval)
            elapsed += interval

        raise TimeoutError(
            f"Instagram container not ready within {max_wait}s "
            f"(creation_id={creation_id})"
        )

    def _publish_media(
        self,
        creation_id: str,
        access_token: str,
        user_id: str,
    ) -> str:
        """Publish the media container as a Reel.

        Returns the media ID of the published Reel.
        """
        resp = self.httpx.post(
            f"{GRAPH_API_BASE}/{user_id}/media_publish",
            params={
                "creation_id": creation_id,
                "access_token": access_token,
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()

        if "id" not in data:
            raise RuntimeError(f"Instagram publish failed: {data}")

        media_id = data["id"]
        log.info("Instagram Reel published: %s", media_id)
        return media_id

    def post_reel(
        self,
        db: Session,
        video_url: str,
        caption: str,
        hashtags: list[str] | None = None,
        post_type: PostType = PostType.VIDEO,
        document_id: int | None = None,
        company_id: int | None = None,
        dry_run: bool = False,
    ) -> str | None:
        """Upload and publish a Reel to Instagram.

        Args:
            video_url: Publicly accessible URL of the video file.
            caption: Caption text for the Reel.
            hashtags: Optional list of hashtags to append.
            post_type: PostType for logging.
            document_id: Optional document ID for deduplication.
            company_id: Optional company ID for logging.
            dry_run: If True, skip actual posting.

        Returns media_id if posted, None if dry_run or duplicate.
        """
        # Check for duplicate
        if document_id is not None:
            existing = (
                db.query(PostLog)
                .filter(
                    PostLog.platform == PostPlatform.INSTAGRAM,
                    PostLog.post_type == post_type,
                    PostLog.document_id == document_id,
                )
                .first()
            )
            if existing:
                log.info(
                    "Instagram Reel already posted for document_id=%s, type=%s",
                    document_id,
                    post_type,
                )
                return None

        # Build full caption with hashtags
        full_caption = caption
        if hashtags:
            tags_str = " ".join(f"#{t.lstrip('#')}" for t in hashtags)
            full_caption = f"{caption}\n\n{tags_str}"

        # Truncate to Instagram caption limit (2200 chars)
        full_caption = full_caption[:2200]

        if dry_run:
            log.info("[DRY-RUN] Would post Instagram Reel: %s", full_caption[:100])
            return None

        access_token, user_id = _get_credentials()

        log.info("Posting Reel to Instagram: %s", caption[:80])

        # Step 1: Create media container
        creation_id = self._create_media_container(
            video_url=video_url,
            caption=full_caption,
            access_token=access_token,
            user_id=user_id,
        )

        # Step 2: Wait for container to finish processing
        self._wait_for_container(creation_id, access_token)

        # Step 3: Publish
        media_id = self._publish_media(creation_id, access_token, user_id)

        # Log to DB
        post_log = PostLog(
            platform=PostPlatform.INSTAGRAM,
            post_type=post_type,
            external_id=media_id,
            document_id=document_id,
            company_id=company_id,
            content_preview=full_caption[:200],
            metadata_={"video_url": video_url, "hashtags": hashtags or []},
        )
        db.add(post_log)
        db.commit()

        log.info("Instagram Reel posted: %s (media_id=%s)", post_type.value, media_id)
        return media_id
