"""
BGM自動ミキシングサービス

ナレーション音声にBGMを自動ミックスする。
- BGMライブラリ管理（mp3/wav/ogg/m4a対応）
- ムードベースのBGM選択
- 自動ダッキング（ナレーション中はBGM音量を下げる）
- 音量ノーマライゼーション（ffmpeg loudnorm）
"""

from __future__ import annotations

import json
import logging
import os
import random
import shutil
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Supported audio extensions
_AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a"}

# Valid mood categories
VALID_MOODS = ("calm", "energetic", "serious", "happy")


class BGMMixer:
    """BGM自動ミキシング＆ダッキング"""

    def __init__(self, bgm_dir: str = "static/bgm") -> None:
        self.bgm_dir = Path(bgm_dir)
        self.bgm_dir.mkdir(parents=True, exist_ok=True)
        self._metadata: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # Metadata helpers
    # ------------------------------------------------------------------

    @property
    def metadata_path(self) -> Path:
        return self.bgm_dir / "bgm_metadata.json"

    def _load_metadata(self) -> dict[str, Any]:
        """Load (and cache) bgm_metadata.json."""
        if self._metadata is not None:
            return self._metadata

        if self.metadata_path.exists():
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                self._metadata = json.load(f)
        else:
            self._metadata = {"tracks": []}

        return self._metadata

    def _save_metadata(self, data: dict[str, Any]) -> None:
        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        self._metadata = data

    # ------------------------------------------------------------------
    # Track listing / selection
    # ------------------------------------------------------------------

    def list_tracks(self, mood: str | None = None) -> list[dict]:
        """
        List available BGM tracks, optionally filtered by mood.

        Combines metadata entries with a filesystem scan so that tracks
        without metadata are still discoverable.
        """
        meta = self._load_metadata()
        tracks_by_name: dict[str, dict] = {
            t["filename"]: t for t in meta.get("tracks", [])
        }

        # Scan directory for actual files
        for p in sorted(self.bgm_dir.iterdir()):
            if p.suffix.lower() in _AUDIO_EXTENSIONS and p.name not in tracks_by_name:
                tracks_by_name[p.name] = {
                    "filename": p.name,
                    "mood": "calm",
                    "bpm": None,
                    "duration": None,
                }

        tracks = list(tracks_by_name.values())

        # Mark which files actually exist on disk
        for t in tracks:
            t["exists"] = (self.bgm_dir / t["filename"]).exists()

        if mood is not None:
            tracks = [t for t in tracks if t.get("mood") == mood]

        return tracks

    def select_track(self, mood: str = "calm", duration: float | None = None) -> str:
        """
        Auto-select a BGM track based on mood.

        If *duration* is given, prefer tracks whose duration >= narration
        duration so the BGM doesn't need looping.

        Returns:
            str: absolute file path of the selected track.

        Raises:
            FileNotFoundError: if no suitable track is found.
        """
        candidates = [t for t in self.list_tracks(mood=mood) if t["exists"]]

        if not candidates:
            # Fallback: any track that exists
            candidates = [t for t in self.list_tracks() if t["exists"]]

        if not candidates:
            raise FileNotFoundError(
                f"No BGM tracks found in {self.bgm_dir}. "
                "Please add music files and update bgm_metadata.json."
            )

        # Prefer tracks long enough
        if duration is not None:
            long_enough = [
                t for t in candidates
                if t.get("duration") is not None and t["duration"] >= duration
            ]
            if long_enough:
                candidates = long_enough

        chosen = random.choice(candidates)
        path = str((self.bgm_dir / chosen["filename"]).resolve())
        logger.info(f"Selected BGM: {chosen['filename']} (mood={chosen.get('mood')})")
        return path

    # ------------------------------------------------------------------
    # Audio duration helper
    # ------------------------------------------------------------------

    @staticmethod
    def _get_duration(audio_path: str) -> float:
        """Get duration of an audio file in seconds using ffprobe."""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path,
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, shell=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed for {audio_path}: {result.stderr}")
        return float(result.stdout.strip())

    # ------------------------------------------------------------------
    # Core mixing
    # ------------------------------------------------------------------

    def mix(
        self,
        narration_path: str,
        bgm_path: str,
        output_path: str,
        bgm_volume: float = 0.1,
        duck_volume: float = 0.05,
        fade_in: float = 2.0,
        fade_out: float = 3.0,
    ) -> str:
        """
        Mix narration + BGM with auto-ducking.

        Strategy:
        1. Use ffmpeg's sidechaincompress to duck BGM when narration is
           present.  This gives smooth, real-time ducking without needing
           to pre-detect silence boundaries.
        2. Apply fade-in / fade-out to the BGM.
        3. Trim BGM to match narration duration (with fade-out).

        Args:
            narration_path: Path to the narration WAV/MP3.
            bgm_path:       Path to the BGM track.
            output_path:    Path for the mixed output file.
            bgm_volume:     Base BGM volume (0.0-1.0) during silence.
            duck_volume:    BGM volume when narration is playing.
            fade_in:        BGM fade-in duration in seconds.
            fade_out:       BGM fade-out duration in seconds.

        Returns:
            str: *output_path* on success.
        """
        if not shutil.which("ffmpeg"):
            raise RuntimeError("ffmpeg not found. Please install ffmpeg.")

        narration_path = str(Path(narration_path).resolve())
        bgm_path = str(Path(bgm_path).resolve())
        output_path_resolved = str(Path(output_path).resolve())
        Path(output_path_resolved).parent.mkdir(parents=True, exist_ok=True)

        narration_dur = self._get_duration(narration_path)

        # Compute ratio for sidechaincompress.
        # A higher ratio ducks the BGM more aggressively.
        # We derive it from the volume ratio so the API feels intuitive.
        if duck_volume > 0 and bgm_volume > 0:
            ratio = max(2, int(bgm_volume / duck_volume))
        else:
            ratio = 20

        # fade-out start time
        fade_out_start = max(0, narration_dur - fade_out)

        # Build the filter_complex:
        # [0:a] = narration
        # [1:a] = BGM
        #
        # 1. Set BGM base volume + fade in/out + trim to narration length
        # 2. Apply sidechaincompress: narration drives the compressor on BGM
        # 3. Mix narration (full volume) + ducked BGM
        filter_complex = (
            # BGM: set volume, loop if needed, trim, fade
            f"[1:a]aloop=loop=-1:size=2e+09:start=0,"
            f"atrim=0:{narration_dur + 1},"
            f"volume={bgm_volume},"
            f"afade=t=in:st=0:d={fade_in},"
            f"afade=t=out:st={fade_out_start}:d={fade_out}"
            f"[bgm];"
            # Sidechain compress: narration controls BGM ducking
            f"[bgm][0:a]sidechaincompress="
            f"threshold=0.02:ratio={ratio}:attack=200:release=1000"
            f"[ducked_bgm];"
            # Mix narration + ducked BGM
            f"[0:a][ducked_bgm]amix=inputs=2:duration=first:dropout_transition=2"
            f"[mixed]"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", narration_path,
            "-i", bgm_path,
            "-filter_complex", filter_complex,
            "-map", "[mixed]",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "44100",
            output_path_resolved,
        ]

        logger.info(
            f"Mixing narration ({narration_dur:.1f}s) + BGM "
            f"(vol={bgm_volume}, duck={duck_volume})"
        )
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300, shell=False,
        )

        if result.returncode != 0:
            logger.error(f"ffmpeg mix failed: {result.stderr[-800:]}")
            raise RuntimeError(f"ffmpeg mix failed: {result.stderr[-500:]}")

        logger.info(f"Mixed audio saved: {output_path_resolved}")
        return output_path_resolved

    # ------------------------------------------------------------------
    # Volume normalization
    # ------------------------------------------------------------------

    def normalize_audio(
        self,
        input_path: str,
        output_path: str | None = None,
        target_lufs: float = -16.0,
    ) -> str:
        """
        Normalize audio levels using ffmpeg loudnorm (two-pass).

        Args:
            input_path:  Source audio file.
            output_path: Destination (defaults to overwriting input via temp).
            target_lufs: Target loudness in LUFS (default -16.0).

        Returns:
            str: Output file path.
        """
        if not shutil.which("ffmpeg"):
            raise RuntimeError("ffmpeg not found. Please install ffmpeg.")

        input_path = str(Path(input_path).resolve())
        in_place = output_path is None
        if in_place:
            output_path = input_path + ".norm.tmp"

        output_resolved = str(Path(output_path).resolve())
        Path(output_resolved).parent.mkdir(parents=True, exist_ok=True)

        # ---- Pass 1: measure loudness ----
        measure_cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11:print_format=json",
            "-f", "null",
            "-",
        ]
        result = subprocess.run(
            measure_cmd, capture_output=True, text=True, timeout=120, shell=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Loudnorm measure failed: {result.stderr[-500:]}")

        # Parse measured values from stderr (ffmpeg outputs to stderr)
        stderr = result.stderr
        try:
            json_start = stderr.rindex("{")
            json_end = stderr.rindex("}") + 1
            measured = json.loads(stderr[json_start:json_end])
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Could not parse loudnorm stats, using single-pass: {e}")
            # Fallback: single-pass normalization
            single_cmd = [
                "ffmpeg", "-y",
                "-i", input_path,
                "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11",
                "-c:a", "aac", "-b:a", "192k",
                output_resolved,
            ]
            result = subprocess.run(
                single_cmd, capture_output=True, text=True, timeout=120, shell=False,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Loudnorm single-pass failed: {result.stderr[-500:]}")

            if in_place:
                os.replace(output_resolved, input_path)
                return input_path
            return output_resolved

        # ---- Pass 2: apply normalization with measured values ----
        loudnorm_filter = (
            f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11"
            f":measured_I={measured['input_i']}"
            f":measured_TP={measured['input_tp']}"
            f":measured_LRA={measured['input_lra']}"
            f":measured_thresh={measured['input_thresh']}"
            f":offset={measured['target_offset']}"
            f":linear=true"
        )

        norm_cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-af", loudnorm_filter,
            "-c:a", "aac", "-b:a", "192k",
            "-ar", "44100",
            output_resolved,
        ]
        result = subprocess.run(
            norm_cmd, capture_output=True, text=True, timeout=120, shell=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Loudnorm apply failed: {result.stderr[-500:]}")

        if in_place:
            os.replace(output_resolved, input_path)
            logger.info(f"Audio normalized in-place: {input_path} (target={target_lufs} LUFS)")
            return input_path

        logger.info(f"Audio normalized: {output_resolved} (target={target_lufs} LUFS)")
        return output_resolved
