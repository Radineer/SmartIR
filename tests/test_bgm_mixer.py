"""Tests for BGMMixer service."""

import json
import pytest
from unittest.mock import MagicMock, patch, call
from pathlib import Path

from app.services.bgm_mixer import BGMMixer, VALID_MOODS


class TestListTracks:
    def test_list_tracks_from_metadata(self, tmp_path):
        """Tracks listed from bgm_metadata.json."""
        bgm_dir = tmp_path / "bgm"
        bgm_dir.mkdir()

        # Create a track file
        (bgm_dir / "calm_track.mp3").write_bytes(b"fake-mp3")

        # Create metadata
        metadata = {
            "tracks": [
                {"filename": "calm_track.mp3", "mood": "calm", "bpm": 80, "duration": 120.0},
            ]
        }
        (bgm_dir / "bgm_metadata.json").write_text(json.dumps(metadata), encoding="utf-8")

        mixer = BGMMixer(bgm_dir=str(bgm_dir))
        tracks = mixer.list_tracks()

        assert len(tracks) == 1
        assert tracks[0]["filename"] == "calm_track.mp3"
        assert tracks[0]["mood"] == "calm"
        assert tracks[0]["exists"] is True

    def test_list_tracks_discovers_files_without_metadata(self, tmp_path):
        """Files on disk without metadata entries are still discovered."""
        bgm_dir = tmp_path / "bgm"
        bgm_dir.mkdir()

        (bgm_dir / "unknown_track.wav").write_bytes(b"fake-wav")

        mixer = BGMMixer(bgm_dir=str(bgm_dir))
        tracks = mixer.list_tracks()

        assert len(tracks) == 1
        assert tracks[0]["filename"] == "unknown_track.wav"
        assert tracks[0]["mood"] == "calm"  # default mood
        assert tracks[0]["exists"] is True

    def test_list_tracks_mood_filter(self, tmp_path):
        """Mood filter returns only matching tracks."""
        bgm_dir = tmp_path / "bgm"
        bgm_dir.mkdir()

        (bgm_dir / "calm1.mp3").write_bytes(b"data")
        (bgm_dir / "energetic1.mp3").write_bytes(b"data")

        metadata = {
            "tracks": [
                {"filename": "calm1.mp3", "mood": "calm"},
                {"filename": "energetic1.mp3", "mood": "energetic"},
            ]
        }
        (bgm_dir / "bgm_metadata.json").write_text(json.dumps(metadata), encoding="utf-8")

        mixer = BGMMixer(bgm_dir=str(bgm_dir))

        calm_tracks = mixer.list_tracks(mood="calm")
        assert len(calm_tracks) == 1
        assert calm_tracks[0]["mood"] == "calm"

        energetic_tracks = mixer.list_tracks(mood="energetic")
        assert len(energetic_tracks) == 1
        assert energetic_tracks[0]["mood"] == "energetic"

    def test_list_tracks_ignores_non_audio_files(self, tmp_path):
        """Non-audio files (e.g., .txt, .json) should not appear in track list."""
        bgm_dir = tmp_path / "bgm"
        bgm_dir.mkdir()

        (bgm_dir / "readme.txt").write_text("not audio")
        (bgm_dir / "real_track.ogg").write_bytes(b"ogg-data")

        mixer = BGMMixer(bgm_dir=str(bgm_dir))
        tracks = mixer.list_tracks()

        filenames = [t["filename"] for t in tracks]
        assert "real_track.ogg" in filenames
        assert "readme.txt" not in filenames

    def test_marks_missing_files(self, tmp_path):
        """Metadata entries for files not on disk get exists=False."""
        bgm_dir = tmp_path / "bgm"
        bgm_dir.mkdir()

        metadata = {
            "tracks": [
                {"filename": "missing.mp3", "mood": "calm"},
            ]
        }
        (bgm_dir / "bgm_metadata.json").write_text(json.dumps(metadata), encoding="utf-8")

        mixer = BGMMixer(bgm_dir=str(bgm_dir))
        tracks = mixer.list_tracks()

        assert len(tracks) == 1
        assert tracks[0]["exists"] is False


class TestSelectTrack:
    def test_select_track_by_mood(self, tmp_path):
        bgm_dir = tmp_path / "bgm"
        bgm_dir.mkdir()

        (bgm_dir / "calm1.mp3").write_bytes(b"data")
        (bgm_dir / "energetic1.mp3").write_bytes(b"data")

        metadata = {
            "tracks": [
                {"filename": "calm1.mp3", "mood": "calm"},
                {"filename": "energetic1.mp3", "mood": "energetic"},
            ]
        }
        (bgm_dir / "bgm_metadata.json").write_text(json.dumps(metadata), encoding="utf-8")

        mixer = BGMMixer(bgm_dir=str(bgm_dir))

        # With only one calm track, selection is deterministic
        path = mixer.select_track(mood="calm")
        assert "calm1.mp3" in path

    def test_select_track_fallback_when_no_mood_match(self, tmp_path):
        """Falls back to any existing track when mood has no matches."""
        bgm_dir = tmp_path / "bgm"
        bgm_dir.mkdir()

        (bgm_dir / "calm1.mp3").write_bytes(b"data")

        metadata = {"tracks": [{"filename": "calm1.mp3", "mood": "calm"}]}
        (bgm_dir / "bgm_metadata.json").write_text(json.dumps(metadata), encoding="utf-8")

        mixer = BGMMixer(bgm_dir=str(bgm_dir))
        path = mixer.select_track(mood="energetic")
        assert "calm1.mp3" in path

    def test_select_track_raises_when_no_tracks(self, tmp_path):
        bgm_dir = tmp_path / "bgm"
        bgm_dir.mkdir()

        mixer = BGMMixer(bgm_dir=str(bgm_dir))
        with pytest.raises(FileNotFoundError, match="No BGM tracks found"):
            mixer.select_track()

    def test_select_track_prefers_long_enough(self, tmp_path):
        bgm_dir = tmp_path / "bgm"
        bgm_dir.mkdir()

        (bgm_dir / "short.mp3").write_bytes(b"data")
        (bgm_dir / "long.mp3").write_bytes(b"data")

        metadata = {
            "tracks": [
                {"filename": "short.mp3", "mood": "calm", "duration": 30.0},
                {"filename": "long.mp3", "mood": "calm", "duration": 180.0},
            ]
        }
        (bgm_dir / "bgm_metadata.json").write_text(json.dumps(metadata), encoding="utf-8")

        mixer = BGMMixer(bgm_dir=str(bgm_dir))
        path = mixer.select_track(mood="calm", duration=120.0)
        assert "long.mp3" in path


class TestMix:
    @patch("shutil.which", return_value="/usr/bin/ffmpeg")
    @patch("subprocess.run")
    @patch.object(BGMMixer, "_get_duration", return_value=60.0)
    def test_mix_ffmpeg_command(self, mock_duration, mock_run, mock_which, tmp_path):
        """Verify ffmpeg is called with correct args for mixing."""
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        mixer = BGMMixer(bgm_dir=str(tmp_path / "bgm"))

        narration = tmp_path / "narration.wav"
        narration.write_bytes(b"fake")
        bgm = tmp_path / "bgm_track.mp3"
        bgm.write_bytes(b"fake")
        output = tmp_path / "output.aac"

        result = mixer.mix(
            narration_path=str(narration),
            bgm_path=str(bgm),
            output_path=str(output),
            bgm_volume=0.1,
            duck_volume=0.05,
        )

        # ffmpeg should have been called
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]

        assert cmd[0] == "ffmpeg"
        assert "-y" in cmd
        assert "-filter_complex" in cmd
        assert "-c:a" in cmd
        assert "aac" in cmd

        # Check that both input files are in the command
        assert str(narration.resolve()) in cmd
        assert str(bgm.resolve()) in cmd

        # Check filter contains sidechaincompress
        filter_idx = cmd.index("-filter_complex") + 1
        filter_str = cmd[filter_idx]
        assert "sidechaincompress" in filter_str
        assert "amix" in filter_str

    @patch("shutil.which", return_value=None)
    def test_mix_raises_when_ffmpeg_missing(self, mock_which, tmp_path):
        mixer = BGMMixer(bgm_dir=str(tmp_path / "bgm"))
        with pytest.raises(RuntimeError, match="ffmpeg not found"):
            mixer.mix("narration.wav", "bgm.mp3", "output.aac")

    @patch("shutil.which", return_value="/usr/bin/ffmpeg")
    @patch("subprocess.run")
    @patch.object(BGMMixer, "_get_duration", return_value=60.0)
    def test_mix_raises_on_ffmpeg_failure(self, mock_duration, mock_run, mock_which, tmp_path):
        mock_run.return_value = MagicMock(returncode=1, stderr="error details")

        mixer = BGMMixer(bgm_dir=str(tmp_path / "bgm"))

        narration = tmp_path / "narration.wav"
        narration.write_bytes(b"fake")
        bgm = tmp_path / "bgm.mp3"
        bgm.write_bytes(b"fake")

        with pytest.raises(RuntimeError, match="ffmpeg mix failed"):
            mixer.mix(str(narration), str(bgm), str(tmp_path / "out.aac"))


class TestNormalizeAudio:
    @patch("shutil.which", return_value="/usr/bin/ffmpeg")
    @patch("subprocess.run")
    def test_normalize_two_pass(self, mock_run, mock_which, tmp_path):
        """Two-pass normalization: measure then apply."""
        measure_json = json.dumps({
            "input_i": "-24.0",
            "input_tp": "-2.0",
            "input_lra": "7.0",
            "input_thresh": "-34.0",
            "target_offset": "0.5",
        })
        # First call: measure (pass 1) - stderr contains JSON
        # Second call: apply (pass 2) - success
        mock_run.side_effect = [
            MagicMock(returncode=0, stderr=f"some output\n{measure_json}\n", stdout=""),
            MagicMock(returncode=0, stderr="", stdout=""),
        ]

        mixer = BGMMixer(bgm_dir=str(tmp_path / "bgm"))
        input_file = tmp_path / "audio.wav"
        input_file.write_bytes(b"fake")
        output_file = tmp_path / "normalized.aac"

        result = mixer.normalize_audio(str(input_file), str(output_file))

        assert mock_run.call_count == 2
        # Second call should contain measured values
        second_cmd = mock_run.call_args_list[1][0][0]
        filter_str = " ".join(second_cmd)
        assert "measured_I" in filter_str
        assert "linear=true" in filter_str

    @patch("shutil.which", return_value=None)
    def test_normalize_raises_when_ffmpeg_missing(self, mock_which, tmp_path):
        mixer = BGMMixer(bgm_dir=str(tmp_path / "bgm"))
        with pytest.raises(RuntimeError, match="ffmpeg not found"):
            mixer.normalize_audio("input.wav")

    @patch("shutil.which", return_value="/usr/bin/ffmpeg")
    @patch("subprocess.run")
    def test_normalize_fallback_single_pass(self, mock_run, mock_which, tmp_path):
        """Falls back to single-pass when JSON parsing fails."""
        # First call: measure fails to produce valid JSON
        # Second call: single-pass succeeds
        mock_run.side_effect = [
            MagicMock(returncode=0, stderr="no json here at all", stdout=""),
            MagicMock(returncode=0, stderr="", stdout=""),
        ]

        mixer = BGMMixer(bgm_dir=str(tmp_path / "bgm"))
        input_file = tmp_path / "audio.wav"
        input_file.write_bytes(b"fake")
        output_file = tmp_path / "normalized.aac"

        result = mixer.normalize_audio(str(input_file), str(output_file))
        assert mock_run.call_count == 2
