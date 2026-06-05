"""Tests for TwitterClient."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import date

from app.social.twitter import TwitterClient
from app.models.post_log import PostLog, PostPlatform, PostType


class TestTwitterClient:
    def setup_method(self):
        self.client = TwitterClient()
        self.db = MagicMock()

    def test_post_dry_run(self):
        # Dry run should not call tweepy
        self.db.query.return_value.filter.return_value.first.return_value = None

        result = self.client.post(
            db=self.db,
            text="test tweet",
            post_type=PostType.BREAKING,
            document_id=1,
            dry_run=True,
        )
        assert result is None
        self.db.add.assert_not_called()

    def test_post_duplicate_detection(self):
        # Return existing log
        self.db.query.return_value.filter.return_value.first.return_value = PostLog(
            platform=PostPlatform.TWITTER,
            post_type=PostType.BREAKING,
            document_id=1,
        )

        result = self.client.post(
            db=self.db,
            text="test tweet",
            post_type=PostType.BREAKING,
            document_id=1,
        )
        assert result is None

    @patch.dict("os.environ", {
        "TWITTER_API_KEY": "key",
        "TWITTER_API_SECRET": "secret",
        "TWITTER_ACCESS_TOKEN": "token",
        "TWITTER_ACCESS_SECRET": "secret",
    })
    @patch("app.social.twitter._get_client")
    def test_post_success(self, mock_get_client):
        mock_tweepy = MagicMock()
        mock_tweepy.create_tweet.return_value = MagicMock(data={"id": "12345"})
        mock_get_client.return_value = mock_tweepy

        self.db.query.return_value.filter.return_value.first.return_value = None
        self.client._client = mock_tweepy

        result = self.client.post(
            db=self.db,
            text="test tweet",
            post_type=PostType.BREAKING,
            document_id=1,
            company_id=1,
        )
        assert result == "12345"
        self.db.add.assert_called_once()
        self.db.commit.assert_called_once()

    def test_post_daily_dry_run(self):
        self.db.query.return_value.filter.return_value.first.return_value = None

        result = self.client.post_daily(
            db=self.db,
            text="daily summary",
            target_date=date(2026, 3, 6),
            dry_run=True,
        )
        assert result is None


class TestPostLogModel:
    def test_enum_values(self):
        assert PostPlatform.NOTE.value == "note"
        assert PostPlatform.TWITTER.value == "twitter"
        assert PostType.BREAKING.value == "breaking"
        assert PostType.ANALYSIS.value == "analysis"
        assert PostType.DAILY_SUMMARY.value == "daily"
        assert PostType.WEEKLY_SUMMARY.value == "weekly"
