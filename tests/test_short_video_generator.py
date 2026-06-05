"""Tests for ShortVideoGenerator service."""

import json
import pytest
from unittest.mock import MagicMock, patch, ANY
from pathlib import Path

from app.services.short_video_generator import (
    ShortVideoGenerator,
    _escape_drawtext,
    _get_wav_duration,
    IRIS_SYSTEM_PROMPT,
    VIDEO_WIDTH,
    VIDEO_HEIGHT,
    FPS,
)


class TestEscapeDrawtext:
    def test_escapes_colon(self):
        assert "\\:" in _escape_drawtext("time:12:00")

    def test_escapes_semicolon(self):
        assert "\\;" in _escape_drawtext("a;b")

    def test_escapes_backslash(self):
        assert "\\\\" in _escape_drawtext("path\\to")

    def test_escapes_single_quote(self):
        result = _escape_drawtext("it's")
        assert "'" in result  # escaped form


class TestGenerateHighlightScript:
    def setup_method(self):
        self.gen = ShortVideoGenerator(output_dir="/tmp/test_shorts")

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("anthropic.Anthropic")
    def test_generate_highlight_script(self, MockAnthropic):
        """Verify the script generation calls Claude with correct params."""
        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Generated narration script\nLine two")]
        mock_client.messages.create.return_value = mock_response

        analysis = {
            "company_name": "Toyota",
            "ticker_code": "7203",
            "summary": "Strong quarterly results with revenue growth.",
            "key_points": ["Revenue up 15%", "New EV lineup"],
            "sentiment": {"positive": "0.75", "negative": "0.25"},
        }

        result = self.gen.generate_highlight_script(analysis, max_seconds=30)

        assert result == "Generated narration script\nLine two"
        mock_client.messages.create.assert_called_once()

        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["model"] == "claude-sonnet-4-20250514"
        assert call_kwargs["system"] == IRIS_SYSTEM_PROMPT
        assert call_kwargs["temperature"] == 0.7

        # Verify prompt contains analysis data
        user_msg = call_kwargs["messages"][0]["content"]
        assert "Toyota" in user_msg
        assert "7203" in user_msg
        assert "Revenue up 15%" in user_msg

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("anthropic.Anthropic")
    def test_generate_script_handles_string_key_points(self, MockAnthropic):
        """key_points as JSON string should be parsed."""
        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Script text")]
        mock_client.messages.create.return_value = mock_response

        analysis = {
            "company_name": "Test Corp",
            "ticker_code": "0001",
            "summary": "Summary",
            "key_points": json.dumps(["Point A", "Point B"]),
            "sentiment": json.dumps({"positive": "0.5", "negative": "0.5"}),
        }

        result = self.gen.generate_highlight_script(analysis)
        assert result == "Script text"

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("anthropic.Anthropic")
    def test_generate_script_with_empty_analysis(self, MockAnthropic):
        """Handles missing fields gracefully."""
        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Fallback script")]
        mock_client.messages.create.return_value = mock_response

        analysis = {}  # completely empty

        result = self.gen.generate_highlight_script(analysis)
        assert result == "Fallback script"


class TestAssembleVideo:
    def setup_method(self):
        self.gen = ShortVideoGenerator(output_dir="/tmp/test_shorts")

    @patch("subprocess.run")
    def test_assemble_video_ffmpeg_args(self, mock_run, tmp_path):
        """Verify ffmpeg is called with correct arguments."""
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        audio_path = str(tmp_path / "narration.wav")
        subtitle_path = str(tmp_path / "subs.ass")
        output_path = str(tmp_path / "output.mp4")

        # Create dummy files
        Path(audio_path).write_bytes(b"fake")
        Path(subtitle_path).write_text("fake ass")

        result = self.gen.assemble_video(
            audio_path=audio_path,
            subtitle_path=subtitle_path,
            title="Test Video",
            output_path=output_path,
            company_name="Toyota",
            ticker_code="7203",
            sentiment={"positive": "0.7", "negative": "0.3"},
            duration=30.0,
        )

        assert result == output_path
        mock_run.assert_called_once()

        cmd = mock_run.call_args[0][0]

        # Core ffmpeg arguments
        assert cmd[0] == "ffmpeg"
        assert "-y" in cmd
        assert "-filter_complex" in cmd
        assert "-c:v" in cmd
        assert "libx264" in cmd
        assert "-c:a" in cmd
        assert "aac" in cmd
        assert "-pix_fmt" in cmd
        assert "yuv420p" in cmd
        assert "-movflags" in cmd

        # Check filter_complex contains expected filters
        filter_idx = cmd.index("-filter_complex") + 1
        filter_str = cmd[filter_idx]
        assert "drawtext" in filter_str
        assert "sidechaincompress" not in filter_str  # that's bgm_mixer
        assert "ass=" in filter_str  # subtitle overlay

    @patch("subprocess.run")
    def test_assemble_video_with_character_image(self, mock_run, tmp_path):
        """When character image is provided, extra overlay filter is added."""
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        # Create a real dummy image file
        char_img = tmp_path / "iris.png"
        char_img.write_bytes(b"fake-png")

        audio_path = str(tmp_path / "narration.wav")
        Path(audio_path).write_bytes(b"fake")
        subtitle_path = str(tmp_path / "subs.ass")
        Path(subtitle_path).write_text("fake")

        self.gen.assemble_video(
            audio_path=audio_path,
            subtitle_path=subtitle_path,
            title="Test",
            output_path=str(tmp_path / "out.mp4"),
            character_image=str(char_img),
            duration=10.0,
        )

        cmd = mock_run.call_args[0][0]
        # Should have the character image as an input
        assert str(char_img) in cmd
        # Filter should contain overlay for character
        filter_idx = cmd.index("-filter_complex") + 1
        filter_str = cmd[filter_idx]
        assert "overlay" in filter_str

    @patch("subprocess.run")
    def test_assemble_video_without_company_name(self, mock_run, tmp_path):
        """When company_name is empty, company drawtext is omitted."""
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        audio_path = str(tmp_path / "narration.wav")
        Path(audio_path).write_bytes(b"fake")
        subtitle_path = str(tmp_path / "subs.ass")
        Path(subtitle_path).write_text("fake")

        self.gen.assemble_video(
            audio_path=audio_path,
            subtitle_path=subtitle_path,
            title="No Company",
            output_path=str(tmp_path / "out.mp4"),
            company_name="",
            duration=10.0,
        )

        cmd = mock_run.call_args[0][0]
        filter_idx = cmd.index("-filter_complex") + 1
        filter_str = cmd[filter_idx]
        # Should still have title drawtext but skip company drawtext label
        assert "with_title" in filter_str

    @patch("subprocess.run")
    def test_assemble_video_ffmpeg_failure(self, mock_run, tmp_path):
        """RuntimeError raised when ffmpeg exits non-zero."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="encoding failed",
            stdout="",
        )

        audio_path = str(tmp_path / "narration.wav")
        Path(audio_path).write_bytes(b"fake")
        subtitle_path = str(tmp_path / "subs.ass")
        Path(subtitle_path).write_text("fake")

        with pytest.raises(RuntimeError, match="ffmpeg failed"):
            self.gen.assemble_video(
                audio_path=audio_path,
                subtitle_path=subtitle_path,
                title="Fail",
                output_path=str(tmp_path / "out.mp4"),
                duration=10.0,
            )

    @patch("subprocess.run")
    def test_assemble_video_sentiment_indicators(self, mock_run, tmp_path):
        """Positive/negative sentiment adds colored indicator text."""
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        audio_path = str(tmp_path / "narration.wav")
        Path(audio_path).write_bytes(b"fake")
        subtitle_path = str(tmp_path / "subs.ass")
        Path(subtitle_path).write_text("fake")

        # Positive sentiment
        self.gen.assemble_video(
            audio_path=audio_path,
            subtitle_path=subtitle_path,
            title="Positive",
            output_path=str(tmp_path / "pos.mp4"),
            sentiment={"positive": "0.8", "negative": "0.2"},
            duration=10.0,
        )

        cmd = mock_run.call_args[0][0]
        filter_idx = cmd.index("-filter_complex") + 1
        filter_str = cmd[filter_idx]
        assert "with_sentiment" in filter_str
        assert "0x00E676" in filter_str  # green for positive


class TestHelpers:
    def test_generate_title_highlight_positive(self):
        gen = ShortVideoGenerator(output_dir="/tmp/test")
        analysis = {
            "company_name": "Sony",
            "ticker_code": "6758",
            "sentiment": {"positive": "0.8", "negative": "0.2"},
        }
        title = gen._generate_title(analysis, "highlight")
        assert "Sony" in title
        assert "6758" in title

    def test_generate_title_summary_style(self):
        gen = ShortVideoGenerator(output_dir="/tmp/test")
        analysis = {
            "company_name": "Sony",
            "ticker_code": "6758",
            "sentiment": {},
        }
        title = gen._generate_title(analysis, "summary")
        assert "まとめ" in title

    def test_generate_hashtags(self):
        gen = ShortVideoGenerator(output_dir="/tmp/test")
        analysis = {
            "company_name": "Toyota",
            "ticker_code": "7203",
        }
        tags = gen._generate_hashtags(analysis)
        assert "#株式投資" in tags
        assert "#Toyota" in tags
        assert "#7203" in tags
        # No empty tags
        assert "" not in tags

    def test_wrap_text_short(self):
        result = ShortVideoGenerator._wrap_text("short", max_width=20)
        assert result == "short"

    def test_wrap_text_long(self):
        result = ShortVideoGenerator._wrap_text("a" * 40, max_width=20)
        assert "\\N" in result

    def test_seconds_to_ass_time(self):
        assert ShortVideoGenerator._seconds_to_ass_time(0.0) == "0:00:00.00"
        assert ShortVideoGenerator._seconds_to_ass_time(65.5) == "0:01:05.50"
        assert ShortVideoGenerator._seconds_to_ass_time(3661.25) == "1:01:01.25"
