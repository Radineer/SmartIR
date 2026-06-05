"""Tests for SocialPublisher."""

import pytest
from unittest.mock import MagicMock, patch

from app.social.publisher import SocialPublisher, _PLATFORM_CREDENTIALS
from app.models.post_log import PostType


class TestGetAvailablePlatforms:
    def setup_method(self):
        self.db = MagicMock()
        self.publisher = SocialPublisher(db=self.db)

    @patch.dict("os.environ", {}, clear=True)
    def test_no_platforms_when_no_env_vars(self):
        available = self.publisher.get_available_platforms()
        assert available == []

    @patch.dict("os.environ", {
        "TWITTER_API_KEY": "k",
        "TWITTER_API_SECRET": "s",
        "TWITTER_ACCESS_TOKEN": "t",
        "TWITTER_ACCESS_SECRET": "s",
    }, clear=True)
    def test_twitter_available_when_all_vars_set(self):
        available = self.publisher.get_available_platforms()
        assert "twitter" in available

    @patch.dict("os.environ", {
        "TWITTER_API_KEY": "k",
        # Missing TWITTER_API_SECRET
        "TWITTER_ACCESS_TOKEN": "t",
        "TWITTER_ACCESS_SECRET": "s",
    }, clear=True)
    def test_twitter_not_available_when_partial_vars(self):
        available = self.publisher.get_available_platforms()
        assert "twitter" not in available

    @patch.dict("os.environ", {
        "TIKTOK_ACCESS_TOKEN": "tok",
    }, clear=True)
    def test_tiktok_available(self):
        available = self.publisher.get_available_platforms()
        assert "tiktok" in available

    @patch.dict("os.environ", {
        "INSTAGRAM_ACCESS_TOKEN": "tok",
        "INSTAGRAM_USER_ID": "uid",
    }, clear=True)
    def test_instagram_available(self):
        available = self.publisher.get_available_platforms()
        assert "instagram" in available

    @patch.dict("os.environ", {
        "TWITTER_API_KEY": "k",
        "TWITTER_API_SECRET": "s",
        "TWITTER_ACCESS_TOKEN": "t",
        "TWITTER_ACCESS_SECRET": "s",
        "TIKTOK_ACCESS_TOKEN": "tok",
        "INSTAGRAM_ACCESS_TOKEN": "tok",
        "INSTAGRAM_USER_ID": "uid",
    })
    def test_multiple_platforms_available(self):
        available = self.publisher.get_available_platforms()
        assert "twitter" in available
        assert "tiktok" in available
        assert "instagram" in available

    def test_youtube_never_available(self):
        """YouTube has empty credential list, so it's never 'available'."""
        available = self.publisher.get_available_platforms()
        assert "youtube" not in available


class TestPublishText:
    def setup_method(self):
        self.db = MagicMock()
        self.publisher = SocialPublisher(db=self.db)

    @patch.dict("os.environ", {
        "TWITTER_API_KEY": "k",
        "TWITTER_API_SECRET": "s",
        "TWITTER_ACCESS_TOKEN": "t",
        "TWITTER_ACCESS_SECRET": "s",
    })
    def test_publish_text_delegates_to_twitter(self):
        mock_twitter = MagicMock()
        mock_twitter.post.return_value = "tweet_12345"
        self.publisher._twitter = mock_twitter

        results = self.publisher.publish_text(
            text="Hello world",
            platforms=["twitter"],
            post_type=PostType.ANALYSIS,
        )

        assert results["twitter"]["status"] == "success"
        assert results["twitter"]["id"] == "tweet_12345"
        mock_twitter.post.assert_called_once()

    @patch.dict("os.environ", {}, clear=True)
    def test_publish_text_skips_when_no_credentials(self):
        results = self.publisher.publish_text(
            text="Hello world",
            platforms=["twitter"],
        )

        assert results["twitter"]["status"] == "skipped"
        assert "Credentials" in results["twitter"]["error"]

    @patch.dict("os.environ", {
        "TWITTER_API_KEY": "k",
        "TWITTER_API_SECRET": "s",
        "TWITTER_ACCESS_TOKEN": "t",
        "TWITTER_ACCESS_SECRET": "s",
    })
    def test_publish_text_handles_exception_gracefully(self):
        mock_twitter = MagicMock()
        mock_twitter.post.side_effect = RuntimeError("API rate limit")
        self.publisher._twitter = mock_twitter

        results = self.publisher.publish_text(
            text="Hello world",
            platforms=["twitter"],
        )

        assert results["twitter"]["status"] == "error"
        assert "rate limit" in results["twitter"]["error"]

    def test_publish_text_unsupported_platform(self):
        """Text posting to non-twitter platforms returns 'skipped'."""
        results = self.publisher.publish_text(
            text="Hello",
            platforms=["tiktok"],
            dry_run=True,
        )
        assert results["tiktok"]["status"] == "skipped"


class TestPublishVideo:
    def setup_method(self):
        self.db = MagicMock()
        self.publisher = SocialPublisher(db=self.db)

    @patch.dict("os.environ", {}, clear=True)
    def test_publish_video_skips_unconfigured_platforms(self):
        results = self.publisher.publish_video(
            video_path="/tmp/video.mp4",
            title="Test",
            description="Desc",
            platforms=["tiktok", "instagram"],
        )

        assert results["tiktok"]["status"] == "skipped"
        assert results["instagram"]["status"] == "skipped"

    @patch.dict("os.environ", {"TIKTOK_ACCESS_TOKEN": "tok"})
    def test_publish_video_tiktok_success(self):
        mock_tiktok = MagicMock()
        mock_tiktok.post_video.return_value = "publish_123"
        self.publisher._tiktok = mock_tiktok

        results = self.publisher.publish_video(
            video_path="/tmp/video.mp4",
            title="Test Video",
            description="Desc",
            platforms=["tiktok"],
        )

        assert results["tiktok"]["status"] == "success"
        assert results["tiktok"]["id"] == "publish_123"

    @patch.dict("os.environ", {"TIKTOK_ACCESS_TOKEN": "tok"})
    def test_publish_video_handles_platform_error(self):
        mock_tiktok = MagicMock()
        mock_tiktok.post_video.side_effect = RuntimeError("Upload failed")
        self.publisher._tiktok = mock_tiktok

        results = self.publisher.publish_video(
            video_path="/tmp/video.mp4",
            title="Test",
            description="Desc",
            platforms=["tiktok"],
        )

        assert results["tiktok"]["status"] == "error"
        assert "Upload failed" in results["tiktok"]["error"]

    @patch.dict("os.environ", {
        "INSTAGRAM_ACCESS_TOKEN": "tok",
        "INSTAGRAM_USER_ID": "uid",
    })
    def test_publish_video_instagram_requires_video_url(self):
        """Instagram requires a public video_url, not just a local path."""
        results = self.publisher.publish_video(
            video_path="/tmp/video.mp4",
            title="Test",
            description="Desc",
            platforms=["instagram"],
            video_url=None,
        )

        assert results["instagram"]["status"] == "skipped"
        assert "video_url required" in results["instagram"]["error"]

    @patch.dict("os.environ", {
        "INSTAGRAM_ACCESS_TOKEN": "tok",
        "INSTAGRAM_USER_ID": "uid",
    })
    def test_publish_video_instagram_with_url(self):
        mock_ig = MagicMock()
        mock_ig.post_reel.return_value = "media_456"
        self.publisher._instagram = mock_ig

        results = self.publisher.publish_video(
            video_path="/tmp/video.mp4",
            title="Test",
            description="Desc",
            platforms=["instagram"],
            video_url="https://example.com/video.mp4",
        )

        assert results["instagram"]["status"] == "success"
        assert results["instagram"]["id"] == "media_456"

    def test_publish_video_youtube_not_implemented(self):
        results = self.publisher.publish_video(
            video_path="/tmp/video.mp4",
            title="Test",
            description="Desc",
            platforms=["youtube"],
            dry_run=True,
        )

        assert results["youtube"]["status"] == "skipped"
        assert "not yet implemented" in results["youtube"]["error"]

    def test_publish_video_unknown_platform(self):
        results = self.publisher.publish_video(
            video_path="/tmp/video.mp4",
            title="Test",
            description="Desc",
            platforms=["linkedin"],
            dry_run=True,
        )

        assert results["linkedin"]["status"] == "skipped"
        assert "Unknown" in results["linkedin"]["error"]

    @patch.dict("os.environ", {
        "TIKTOK_ACCESS_TOKEN": "tok",
        "INSTAGRAM_ACCESS_TOKEN": "itok",
        "INSTAGRAM_USER_ID": "uid",
    })
    def test_publish_video_isolates_errors_between_platforms(self):
        """One platform failure should not affect the other."""
        mock_tiktok = MagicMock()
        mock_tiktok.post_video.side_effect = RuntimeError("TikTok down")
        self.publisher._tiktok = mock_tiktok

        mock_ig = MagicMock()
        mock_ig.post_reel.return_value = "media_789"
        self.publisher._instagram = mock_ig

        results = self.publisher.publish_video(
            video_path="/tmp/video.mp4",
            title="Test",
            description="Desc",
            platforms=["tiktok", "instagram"],
            video_url="https://example.com/video.mp4",
        )

        assert results["tiktok"]["status"] == "error"
        assert results["instagram"]["status"] == "success"
