"""Tests for ThumbnailGenerator service."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from PIL import Image

from app.services.thumbnail_generator import (
    ThumbnailGenerator,
    STYLE_PRESETS,
    SENTIMENT_CONFIG,
    WIDTH,
    HEIGHT,
    _load_font,
    _find_system_font,
)


class TestGenerate:
    def setup_method(self):
        # Use font_path=None so it falls back to Pillow default
        # (no system font dependency in tests)
        self.gen = ThumbnailGenerator(font_path="/nonexistent/font.ttf")

    def test_produces_valid_png(self, tmp_path):
        output = str(tmp_path / "thumb.png")
        result = self.gen.generate(
            title="Test Thumbnail",
            style="morning_market",
            output_path=output,
        )
        assert Path(result).exists()

        img = Image.open(result)
        assert img.format == "PNG"
        assert img.size == (WIDTH, HEIGHT)

    def test_all_styles_produce_output(self, tmp_path):
        """Each style preset generates a valid image."""
        for style in STYLE_PRESETS:
            output = str(tmp_path / f"thumb_{style}.png")
            result = self.gen.generate(
                title="Style Test",
                style=style,
                output_path=output,
            )
            assert Path(result).exists()
            img = Image.open(result)
            assert img.size == (WIDTH, HEIGHT)

    def test_different_styles_produce_different_images(self, tmp_path):
        """At minimum, different style presets produce different pixel data."""
        images = {}
        for style in ["morning_market", "ir_analysis", "weekly_summary"]:
            output = str(tmp_path / f"thumb_{style}.png")
            self.gen.generate(
                title="Same Title",
                style=style,
                date_str="2026/01/01",
                output_path=output,
            )
            img = Image.open(output)
            images[style] = img.tobytes()

        # At least two styles should differ (gradient colors differ)
        assert images["morning_market"] != images["ir_analysis"]
        assert images["morning_market"] != images["weekly_summary"]

    def test_unknown_style_falls_back(self, tmp_path):
        """Unknown style gracefully falls back to morning_market."""
        output = str(tmp_path / "thumb.png")
        result = self.gen.generate(
            title="Fallback Test",
            style="nonexistent_style",
            output_path=output,
        )
        assert Path(result).exists()

    def test_with_company_and_ticker(self, tmp_path):
        output = str(tmp_path / "thumb.png")
        result = self.gen.generate(
            title="IR Analysis",
            style="ir_analysis",
            company_name="Toyota Motor",
            ticker_code="7203",
            output_path=output,
        )
        assert Path(result).exists()
        img = Image.open(result)
        assert img.size == (WIDTH, HEIGHT)

    def test_creates_parent_directories(self, tmp_path):
        output = str(tmp_path / "nested" / "deep" / "thumb.png")
        result = self.gen.generate(
            title="Nested Dir Test",
            output_path=output,
        )
        assert Path(result).exists()


class TestSentimentRendering:
    def setup_method(self):
        self.gen = ThumbnailGenerator(font_path="/nonexistent/font.ttf")

    def test_positive_sentiment(self, tmp_path):
        output = str(tmp_path / "positive.png")
        result = self.gen.generate(
            title="Good News",
            sentiment="positive",
            output_path=output,
        )
        assert Path(result).exists()

    def test_negative_sentiment(self, tmp_path):
        output = str(tmp_path / "negative.png")
        result = self.gen.generate(
            title="Bad News",
            sentiment="negative",
            output_path=output,
        )
        assert Path(result).exists()

    def test_neutral_sentiment(self, tmp_path):
        output = str(tmp_path / "neutral.png")
        result = self.gen.generate(
            title="Mixed News",
            sentiment="neutral",
            output_path=output,
        )
        assert Path(result).exists()

    def test_unknown_sentiment_ignored(self, tmp_path):
        """Unknown sentiment value does not crash, just skips indicator."""
        output = str(tmp_path / "unknown.png")
        result = self.gen.generate(
            title="Unknown Sentiment",
            sentiment="very_bullish",
            output_path=output,
        )
        assert Path(result).exists()

    def test_sentiments_produce_different_images(self, tmp_path):
        images = {}
        for sentiment in ["positive", "negative", "neutral"]:
            output = str(tmp_path / f"{sentiment}.png")
            self.gen.generate(
                title="Same Title",
                style="ir_analysis",
                sentiment=sentiment,
                date_str="2026/01/01",
                output_path=output,
            )
            img = Image.open(output)
            images[sentiment] = img.tobytes()

        # Positive and negative should look different (different colors)
        assert images["positive"] != images["negative"]


class TestFontFallback:
    def test_load_font_with_missing_path(self):
        """When font path doesn't exist, should fall back to Pillow default."""
        font = _load_font("/nonexistent/path/font.ttf", 24)
        # Should return some font object (default), not raise
        assert font is not None

    def test_load_font_with_none_path(self):
        """None font path should fall back to Pillow default."""
        font = _load_font(None, 24)
        assert font is not None

    @patch("app.services.thumbnail_generator._FONT_SEARCH_PATHS", [])
    def test_find_system_font_returns_none_when_no_fonts(self):
        """When no system fonts exist, returns None."""
        result = _find_system_font()
        assert result is None

    def test_generator_works_with_no_system_font(self, tmp_path):
        """ThumbnailGenerator still produces output without any system fonts."""
        with patch("app.services.thumbnail_generator._find_system_font", return_value=None):
            gen = ThumbnailGenerator(font_path=None)
            output = str(tmp_path / "no_font.png")
            result = gen.generate(title="No Font Test", output_path=output)
            assert Path(result).exists()


class TestCharacterOverlay:
    def test_no_character_image_still_works(self, tmp_path):
        """When no character images exist, thumbnail still generates."""
        with patch(
            "app.services.thumbnail_generator.CHARACTER_IMAGE_DIR",
            tmp_path / "nonexistent_chars",
        ):
            gen = ThumbnailGenerator(font_path="/nonexistent/font.ttf")
            output = str(tmp_path / "no_char.png")
            result = gen.generate(title="No Character", output_path=output)
            assert Path(result).exists()
