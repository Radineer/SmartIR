"""Unified social media publisher.

Provides a single interface to publish content across multiple platforms
(Twitter, TikTok, Instagram, YouTube). Handles credential detection,
error isolation per platform, and unified result reporting.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from sqlalchemy.orm import Session

from app.models.post_log import PostType

log = logging.getLogger(__name__)

# Platform credential requirements
_PLATFORM_CREDENTIALS = {
    "twitter": ["TWITTER_API_KEY", "TWITTER_API_SECRET", "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_SECRET"],
    "tiktok": ["TIKTOK_ACCESS_TOKEN"],
    "instagram": ["INSTAGRAM_ACCESS_TOKEN", "INSTAGRAM_USER_ID"],
    "youtube": [],  # Placeholder for future YouTube integration
}


class SocialPublisher:
    """Unified interface to post to multiple platforms."""

    def __init__(self, db: Session):
        self.db = db
        self._twitter = None
        self._tiktok = None
        self._instagram = None

    @property
    def twitter(self):
        if self._twitter is None:
            from app.social.twitter import TwitterClient
            self._twitter = TwitterClient()
        return self._twitter

    @property
    def tiktok(self):
        if self._tiktok is None:
            from app.social.tiktok import TikTokClient
            self._tiktok = TikTokClient()
        return self._tiktok

    @property
    def instagram(self):
        if self._instagram is None:
            from app.social.instagram import InstagramClient
            self._instagram = InstagramClient()
        return self._instagram

    def get_available_platforms(self) -> list[str]:
        """Returns platforms with all required credentials configured."""
        available = []
        for platform, env_vars in _PLATFORM_CREDENTIALS.items():
            if not env_vars:
                continue
            if all(os.getenv(var) for var in env_vars):
                available.append(platform)
        return available

    def publish_video(
        self,
        video_path: str,
        title: str,
        description: str,
        platforms: list[str] = ["youtube", "tiktok", "instagram"],
        hashtags: list[str] | None = None,
        post_type: PostType = PostType.VIDEO,
        document_id: int | None = None,
        company_id: int | None = None,
        video_url: str | None = None,
        dry_run: bool = False,
    ) -> dict[str, dict[str, Any]]:
        """Publish video to multiple platforms.

        Args:
            video_path: Local path to the video file.
            title: Video title.
            description: Video description.
            platforms: List of platforms to post to.
            hashtags: Optional hashtags.
            post_type: PostType for logging.
            document_id: Optional document ID for dedup.
            company_id: Optional company ID for logging.
            video_url: Public URL of the video (required for Instagram).
            dry_run: If True, skip actual posting.

        Returns:
            Dict mapping platform name to result dict with keys:
            - status: "success", "skipped", or "error"
            - id: External ID if posted
            - error: Error message if failed
        """
        available = self.get_available_platforms()
        results: dict[str, dict[str, Any]] = {}

        for platform in platforms:
            if platform not in available and not dry_run:
                results[platform] = {
                    "status": "skipped",
                    "error": f"Credentials not configured for {platform}",
                }
                continue

            try:
                if platform == "tiktok":
                    external_id = self.tiktok.post_video(
                        db=self.db,
                        video_path=video_path,
                        title=title,
                        description=description,
                        hashtags=hashtags,
                        post_type=post_type,
                        document_id=document_id,
                        company_id=company_id,
                        dry_run=dry_run,
                    )
                    results[platform] = {
                        "status": "success" if external_id else "skipped",
                        "id": external_id,
                    }

                elif platform == "instagram":
                    if not video_url:
                        results[platform] = {
                            "status": "skipped",
                            "error": "video_url required for Instagram (must be publicly accessible)",
                        }
                        continue

                    caption = f"{title}\n{description}" if description else title
                    external_id = self.instagram.post_reel(
                        db=self.db,
                        video_url=video_url,
                        caption=caption,
                        hashtags=hashtags,
                        post_type=post_type,
                        document_id=document_id,
                        company_id=company_id,
                        dry_run=dry_run,
                    )
                    results[platform] = {
                        "status": "success" if external_id else "skipped",
                        "id": external_id,
                    }

                elif platform == "youtube":
                    # YouTube integration placeholder
                    results[platform] = {
                        "status": "skipped",
                        "error": "YouTube upload not yet implemented",
                    }

                else:
                    results[platform] = {
                        "status": "skipped",
                        "error": f"Unknown video platform: {platform}",
                    }

            except Exception as e:
                log.exception("Failed to publish video to %s", platform)
                results[platform] = {
                    "status": "error",
                    "error": str(e),
                }

        return results

    def publish_text(
        self,
        text: str,
        platforms: list[str] = ["twitter"],
        image_path: str | None = None,
        post_type: PostType = PostType.ANALYSIS,
        document_id: int | None = None,
        company_id: int | None = None,
        dry_run: bool = False,
    ) -> dict[str, dict[str, Any]]:
        """Publish text post to platforms.

        Args:
            text: Text content to post.
            platforms: List of platforms to post to.
            image_path: Optional image to attach (platform-dependent).
            post_type: PostType for logging.
            document_id: Optional document ID for dedup.
            company_id: Optional company ID for logging.
            dry_run: If True, skip actual posting.

        Returns:
            Dict mapping platform name to result dict with keys:
            - status: "success", "skipped", or "error"
            - id: External ID if posted
            - error: Error message if failed
        """
        available = self.get_available_platforms()
        results: dict[str, dict[str, Any]] = {}

        for platform in platforms:
            if platform not in available and not dry_run:
                results[platform] = {
                    "status": "skipped",
                    "error": f"Credentials not configured for {platform}",
                }
                continue

            try:
                if platform == "twitter":
                    external_id = self.twitter.post(
                        db=self.db,
                        text=text,
                        post_type=post_type,
                        document_id=document_id,
                        company_id=company_id,
                        dry_run=dry_run,
                    )
                    results[platform] = {
                        "status": "success" if external_id else "skipped",
                        "id": external_id,
                    }

                else:
                    results[platform] = {
                        "status": "skipped",
                        "error": f"Text posting not supported for {platform}",
                    }

            except Exception as e:
                log.exception("Failed to publish text to %s", platform)
                results[platform] = {
                    "status": "error",
                    "error": str(e),
                }

        return results
