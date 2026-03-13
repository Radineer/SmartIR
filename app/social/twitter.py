"""X (Twitter) client using tweepy.

Lazy-loads tweepy to keep it optional. Uses PostLog DB table
for deduplication and audit trail.

Supports advanced engagement: reply chains, quote reposts, likes, search.
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
    """X投稿クライアント with advanced engagement support."""

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
        post_type: PostType = PostType.DAILY_SUMMARY,
        dry_run: bool = False,
    ) -> str | None:
        """Post a summary tweet (daily/weekly/industry) with deduplication."""
        # Check for duplicate by date + post_type
        existing = (
            db.query(PostLog)
            .filter(
                PostLog.platform == PostPlatform.TWITTER,
                PostLog.post_type == post_type,
                PostLog.metadata_["date"].astext == target_date.isoformat(),
            )
            .first()
        )
        if existing:
            log.info("Tweet already posted for %s (type=%s)", target_date, post_type.value)
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
            content_preview=text[:200],
            metadata_={"date": target_date.isoformat()},
        )
        db.add(post_log)
        db.commit()

        log.info("%s tweet posted (id=%s)", post_type.value, tweet_id)
        return tweet_id

    # ── Advanced engagement methods ───────────────────────────

    def reply_to_tweet(
        self,
        tweet_id: str,
        text: str,
        dry_run: bool = False,
    ) -> str | None:
        """Post a reply to an existing tweet.

        Returns reply_tweet_id if posted, None if dry_run.
        """
        if dry_run:
            log.info("[DRY-RUN] Would reply to %s: %s", tweet_id, text)
            return None

        try:
            response = self.client.create_tweet(text=text, in_reply_to_tweet_id=tweet_id)
            reply_id = str(response.data["id"])
            log.info("Reply posted to %s (reply_id=%s)", tweet_id, reply_id)
            return reply_id
        except Exception as e:
            log.warning("Failed to reply to tweet %s: %s", tweet_id, e)
            return None

    def post_tweet_with_link_reply(
        self,
        db: Session,
        main_text: str,
        link_text: str,
        post_type: PostType,
        document_id: int | None = None,
        company_id: int | None = None,
        dry_run: bool = False,
    ) -> tuple[str | None, str | None]:
        """Post main tweet then self-reply with link (avoids external link penalty).

        Returns (main_tweet_id, reply_tweet_id) tuple.
        """
        main_id = self.post(
            db=db,
            text=main_text,
            post_type=post_type,
            document_id=document_id,
            company_id=company_id,
            dry_run=dry_run,
        )
        if main_id:
            reply_id = self.reply_to_tweet(main_id, link_text, dry_run=dry_run)
            return main_id, reply_id
        return None, None

    def quote_repost(
        self,
        tweet_id: str,
        text: str,
        dry_run: bool = False,
    ) -> str | None:
        """Post a quote repost of an existing tweet.

        Returns our_tweet_id if posted, None if dry_run.
        """
        if dry_run:
            log.info("[DRY-RUN] Would quote tweet %s: %s", tweet_id, text)
            return None

        try:
            response = self.client.create_tweet(text=text, quote_tweet_id=tweet_id)
            our_id = str(response.data["id"])
            log.info("Quote repost of %s posted (id=%s)", tweet_id, our_id)
            return our_id
        except Exception as e:
            log.warning("Failed to quote tweet %s: %s", tweet_id, e)
            return None

    def like_tweet(self, tweet_id: str, dry_run: bool = False) -> bool:
        """Like a tweet.

        Returns True if liked successfully, False otherwise.
        """
        if dry_run:
            log.info("[DRY-RUN] Would like tweet %s", tweet_id)
            return True

        try:
            self.client.like(tweet_id)
            log.info("Liked tweet %s", tweet_id)
            return True
        except Exception as e:
            log.warning("Failed to like tweet %s: %s", tweet_id, e)
            return False

    def search_recent_tweets(self, query: str, max_results: int = 10) -> list[dict]:
        """Search recent tweets.

        Returns list of dicts with id, text, author_id, created_at.
        """
        try:
            response = self.client.search_recent_tweets(
                query=query,
                max_results=max(10, min(max_results, 100)),
                tweet_fields=["created_at", "author_id", "public_metrics"],
            )
            if not response.data:
                return []
            return [
                {
                    "id": str(t.id),
                    "text": t.text,
                    "author_id": str(t.author_id),
                    "created_at": str(t.created_at) if t.created_at else "",
                    "metrics": t.public_metrics or {},
                }
                for t in response.data
            ]
        except Exception as e:
            log.warning("Tweet search failed for '%s': %s", query, e)
            return []

    def get_user_recent_tweets(self, username: str, max_results: int = 5) -> list[dict]:
        """Get recent tweets from a specific user.

        Returns list of dicts with id, text, created_at.
        """
        try:
            user = self.client.get_user(username=username)
            if not user.data:
                log.warning("User not found: %s", username)
                return []

            response = self.client.get_users_tweets(
                id=user.data.id,
                max_results=max(5, min(max_results, 100)),
                tweet_fields=["created_at", "public_metrics"],
            )
            if not response.data:
                return []
            return [
                {
                    "id": str(t.id),
                    "text": t.text,
                    "created_at": str(t.created_at) if t.created_at else "",
                    "metrics": t.public_metrics or {},
                }
                for t in response.data
            ]
        except Exception as e:
            log.warning("Failed to get tweets for @%s: %s", username, e)
            return []
