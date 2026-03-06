"""X (Twitter) client using tweepy.

Lazy-loads tweepy to keep it optional. Uses PostLog DB table
for deduplication and audit trail.
"""

from __future__ import annotations

import logging
import os
from datetime import date

from sqlalchemy.orm import Session

from app.models.post_log import PostLog, PostPlatform, PostType

log = logging.getLogger(__name__)


def _check_tweepy() -> None:
    try:
        import tweepy  # noqa: F401
    except ImportError:
        raise ImportError(
            "X連携には tweepy が必要です。\n"
            "pip install tweepy でインストールしてください。"
        )


def _get_client():
    import tweepy

    api_key = os.getenv("TWITTER_API_KEY")
    api_secret = os.getenv("TWITTER_API_SECRET")
    access_token = os.getenv("TWITTER_ACCESS_TOKEN")
    access_secret = os.getenv("TWITTER_ACCESS_SECRET")

    if not all([api_key, api_secret, access_token, access_secret]):
        raise ValueError(
            "TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, "
            "TWITTER_ACCESS_SECRET を環境変数に設定してください"
        )

    return tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_secret,
    )


class TwitterClient:
    """X投稿クライアント"""

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            _check_tweepy()
            self._client = _get_client()
        return self._client

    def post(
        self,
        db: Session,
        text: str,
        post_type: PostType,
        document_id: int | None = None,
        company_id: int | None = None,
        dry_run: bool = False,
    ) -> str | None:
        """Post a tweet with deduplication and logging.

        Returns tweet_id if posted, None if dry_run or duplicate.
        """
        # Check for duplicate
        existing = (
            db.query(PostLog)
            .filter(
                PostLog.platform == PostPlatform.TWITTER,
                PostLog.post_type == post_type,
                PostLog.document_id == document_id,
            )
            .first()
        )
        if existing and document_id is not None:
            log.info("Tweet already posted for document_id=%s, type=%s", document_id, post_type)
            return None

        if dry_run:
            log.info("[DRY-RUN] Would tweet: %s", text)
            return None

        response = self.client.create_tweet(text=text)
        tweet_id = str(response.data["id"])

        post_log = PostLog(
            platform=PostPlatform.TWITTER,
            post_type=post_type,
            external_id=tweet_id,
            document_id=document_id,
            company_id=company_id,
            content_preview=text[:200],
        )
        db.add(post_log)
        db.commit()

        log.info("Tweet posted: %s (id=%s)", post_type.value, tweet_id)
        return tweet_id

    def post_daily(
        self,
        db: Session,
        text: str,
        target_date: date,
        dry_run: bool = False,
    ) -> str | None:
        """Post a daily/weekly summary tweet (no document_id)."""
        # Check for duplicate by date
        existing = (
            db.query(PostLog)
            .filter(
                PostLog.platform == PostPlatform.TWITTER,
                PostLog.post_type == PostType.DAILY_SUMMARY,
                PostLog.content_preview.like(f"%{target_date.isoformat()}%"),
            )
            .first()
        )
        if existing:
            log.info("Daily tweet already posted for %s", target_date)
            return None

        if dry_run:
            log.info("[DRY-RUN] Would tweet: %s", text)
            return None

        response = self.client.create_tweet(text=text)
        tweet_id = str(response.data["id"])

        post_log = PostLog(
            platform=PostPlatform.TWITTER,
            post_type=PostType.DAILY_SUMMARY,
            external_id=tweet_id,
            content_preview=text[:200],
            metadata_={"date": target_date.isoformat()},
        )
        db.add(post_log)
        db.commit()

        log.info("Daily tweet posted (id=%s)", tweet_id)
        return tweet_id
