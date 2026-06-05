"""
Subtitle generator for IR broadcast videos.

Generates SRT/VTT subtitle files from audio (via faster-whisper STT)
or from pre-timed text segments (for TTS-generated audio where timing
is already known).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _format_srt_time(seconds: float) -> str:
    """Format seconds as SRT timestamp: HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _format_vtt_time(seconds: float) -> str:
    """Format seconds as WebVTT timestamp: HH:MM:SS.mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


class SubtitleGenerator:
    """
    Generate SRT/VTT subtitle files from audio or pre-timed segments.

    Uses faster-whisper for local speech-to-text when generating from audio.
    Also provides utilities to convert between subtitle formats.
    """

    def __init__(
        self,
        model_size: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
    ):
        """
        Initialize the subtitle generator.

        Args:
            model_size: Whisper model size (tiny, base, small, medium, large-v3).
            device: Device to run inference on (cpu, cuda).
            compute_type: Quantization type (int8, float16, float32).
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None  # lazy-loaded

    def _get_model(self):
        """Lazy-load the WhisperModel to avoid import cost at init."""
        if self._model is None:
            from faster_whisper import WhisperModel

            logger.info(
                f"Loading faster-whisper model: {self.model_size} "
                f"(device={self.device}, compute_type={self.compute_type})"
            )
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            logger.info("faster-whisper model loaded")
        return self._model

    def from_audio(
        self,
        audio_path: str,
        output_path: str,
        language: str = "ja",
    ) -> str:
        """
        Generate an SRT subtitle file from an audio file using Whisper STT.

        Args:
            audio_path: Path to the input audio file (WAV, MP3, etc.).
            output_path: Path for the output SRT file.
            language: Language code for transcription (default: "ja").

        Returns:
            str: Absolute path to the generated SRT file.
        """
        audio_path = str(audio_path)
        output_path = str(output_path)

        model = self._get_model()

        logger.info(f"Transcribing audio: {audio_path} (language={language})")
        segments_iter, info = model.transcribe(
            audio_path,
            language=language,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=500,
                speech_pad_ms=200,
            ),
        )

        logger.info(
            f"Detected language: {info.language} "
            f"(probability={info.language_probability:.2f})"
        )

        # Collect segments from the iterator
        segments: list[dict] = []
        for seg in segments_iter:
            segments.append({
                "text": seg.text.strip(),
                "start": seg.start,
                "end": seg.end,
            })

        if not segments:
            logger.warning("No speech segments detected in audio")
            segments = [{"text": "...", "start": 0.0, "end": 1.0}]

        logger.info(f"Transcribed {len(segments)} segments")

        return self.from_segments(segments, output_path)

    def from_segments(
        self,
        segments: list[dict],
        output_path: str,
    ) -> str:
        """
        Generate an SRT subtitle file from pre-timed text segments.

        Args:
            segments: List of dicts with keys "text", "start", "end".
                      start/end are in seconds (float).
            output_path: Path for the output SRT file.

        Returns:
            str: Absolute path to the generated SRT file.
        """
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        lines: list[str] = []
        for i, seg in enumerate(segments, start=1):
            text = seg["text"].strip()
            if not text:
                continue

            start_ts = _format_srt_time(seg["start"])
            end_ts = _format_srt_time(seg["end"])

            lines.append(str(i))
            lines.append(f"{start_ts} --> {end_ts}")
            lines.append(text)
            lines.append("")  # blank line between cues

        srt_content = "\n".join(lines)
        output.write_text(srt_content, encoding="utf-8")

        logger.info(f"SRT saved: {output} ({len(segments)} cues)")
        return str(output.resolve())

    def srt_to_vtt(
        self,
        srt_path: str,
        vtt_path: str | None = None,
    ) -> str:
        """
        Convert an SRT file to WebVTT format.

        Args:
            srt_path: Path to the input SRT file.
            vtt_path: Path for the output VTT file.
                      Defaults to the same name with .vtt extension.

        Returns:
            str: Absolute path to the generated VTT file.
        """
        srt_file = Path(srt_path)
        if vtt_path is None:
            vtt_file = srt_file.with_suffix(".vtt")
        else:
            vtt_file = Path(vtt_path)

        vtt_file.parent.mkdir(parents=True, exist_ok=True)

        srt_content = srt_file.read_text(encoding="utf-8")

        # Replace SRT timestamp commas with VTT dots
        vtt_content = re.sub(
            r"(\d{2}:\d{2}:\d{2}),(\d{3})",
            r"\1.\2",
            srt_content,
        )

        # Remove cue numbers (lines that are just digits before timestamps)
        vtt_content = re.sub(
            r"^\d+\s*\n(?=\d{2}:\d{2}:\d{2})",
            "",
            vtt_content,
            flags=re.MULTILINE,
        )

        # Add WebVTT header
        vtt_content = "WEBVTT\n\n" + vtt_content.lstrip("\n")

        vtt_file.write_text(vtt_content, encoding="utf-8")

        logger.info(f"VTT saved: {vtt_file}")
        return str(vtt_file.resolve())
