"""統合TTSサービス - VOICEVOX/AivisSpeech/edge-tts対応

優先順位:
1. AivisSpeech (localhost:10101)
2. VOICEVOX (localhost:50021)
3. edge-tts (Microsoft, ネットワーク経由, フォールバック)
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import wave
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# Engine config
AIVISSPEECH_HOST = os.getenv("AIVISSPEECH_HOST", "http://localhost:10101")
VOICEVOX_HOST = os.getenv("VOICEVOX_HOST", "http://localhost:50021")
AIVIS_SPEAKER_ID = int(os.getenv("AIVIS_SPEAKER_ID", "1878365376"))
VOICEVOX_SPEAKER_ID = int(os.getenv("VOICEVOX_SPEAKER_ID", "3"))
EDGE_TTS_VOICE = os.getenv("EDGE_TTS_VOICE", "ja-JP-NanamiNeural")
TTS_SPEED = float(os.getenv("TTS_SPEED", "1.15"))


def _check_engine(host: str) -> bool:
    """Check if a TTS engine is running."""
    try:
        r = httpx.get(f"{host}/version", timeout=3.0)
        return r.status_code == 200
    except Exception:
        return False


def _detect_engine() -> tuple[str, str, int]:
    """Detect best available TTS engine. Returns (engine_name, host, speaker_id)."""
    if _check_engine(AIVISSPEECH_HOST):
        return ("aivisspeech", AIVISSPEECH_HOST, AIVIS_SPEAKER_ID)
    if _check_engine(VOICEVOX_HOST):
        return ("voicevox", VOICEVOX_HOST, VOICEVOX_SPEAKER_ID)
    return ("edge-tts", "", 0)


def _synthesize_voicevox(text: str, host: str, speaker_id: int) -> bytes:
    """Synthesize via VOICEVOX/AivisSpeech REST API. Returns WAV bytes."""
    with httpx.Client(timeout=60.0) as client:
        # audio_query
        qr = client.post(f"{host}/audio_query", params={"text": text, "speaker": speaker_id})
        qr.raise_for_status()
        query = qr.json()
        query["speedScale"] = TTS_SPEED

        # synthesis
        sr = client.post(f"{host}/synthesis", params={"speaker": speaker_id}, json=query)
        sr.raise_for_status()
        return sr.content


def _synthesize_edge_tts(text: str) -> bytes:
    """Synthesize via edge-tts. Returns WAV bytes."""
    import edge_tts
    import tempfile

    async def _run():
        comm = edge_tts.Communicate(text, EDGE_TTS_VOICE, rate="+10%")
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            mp3_path = f.name
        await comm.save(mp3_path)
        return mp3_path

    mp3_path = asyncio.run(_run())

    # Convert MP3 to WAV via ffmpeg
    import subprocess
    import tempfile as tf
    wav_path = tf.mktemp(suffix=".wav")
    subprocess.run(
        [os.getenv("FFMPEG_PATH", "/opt/homebrew/Cellar/ffmpeg/8.1/bin/ffmpeg"), "-y", "-i", mp3_path, "-ar", "24000", "-ac", "1", "-f", "wav", wav_path],
        capture_output=True, check=True,
    )
    os.unlink(mp3_path)

    with open(wav_path, "rb") as f:
        data = f.read()
    os.unlink(wav_path)
    return data


def get_wav_duration(wav_data: bytes) -> float:
    """Get duration of WAV data in seconds."""
    with wave.open(io.BytesIO(wav_data), "rb") as wf:
        return wf.getnframes() / wf.getframerate() if wf.getframerate() else 0.0


class TTSService:
    """Unified TTS service with auto-detection and fallback."""

    def __init__(self, engine: str | None = None):
        if engine:
            if engine == "edge-tts":
                self.engine, self.host, self.speaker_id = "edge-tts", "", 0
            elif engine == "aivisspeech":
                self.engine, self.host, self.speaker_id = "aivisspeech", AIVISSPEECH_HOST, AIVIS_SPEAKER_ID
            else:
                self.engine, self.host, self.speaker_id = "voicevox", VOICEVOX_HOST, VOICEVOX_SPEAKER_ID
        else:
            self.engine, self.host, self.speaker_id = _detect_engine()
        logger.info("TTS engine: %s (host=%s, speaker=%s)", self.engine, self.host, self.speaker_id)

    def synthesize(self, text: str) -> bytes:
        """Synthesize text to WAV bytes. Auto-fallback to edge-tts on failure."""
        if self.engine in ("voicevox", "aivisspeech"):
            try:
                return _synthesize_voicevox(text, self.host, self.speaker_id)
            except Exception as e:
                logger.warning("VOICEVOX/AivisSpeech failed, falling back to edge-tts: %s", e)
                return _synthesize_edge_tts(text)
        return _synthesize_edge_tts(text)

    def synthesize_to_file(self, text: str, output_path: str) -> float:
        """Synthesize and save to file. Returns duration in seconds."""
        wav_data = self.synthesize(text)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(wav_data)
        return get_wav_duration(wav_data)

    def synthesize_segments(
        self, segments: list[dict], output_dir: str
    ) -> list[dict]:
        """
        Synthesize multiple segments.

        Input:  [{"id": "seg_01", "text": "...", "expression": "analysis"}, ...]
        Output: Same dicts with added "audio_path" and "duration" fields.
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        results = []
        for seg in segments:
            seg_id = seg.get("id", f"seg_{len(results):03d}")
            audio_path = os.path.join(output_dir, f"{seg_id}.wav")
            duration = self.synthesize_to_file(seg["text"], audio_path)
            results.append({**seg, "audio_path": audio_path, "duration": duration})
            logger.info("Segment %s: %.1fs (%s)", seg_id, duration, seg.get("expression", ""))
        return results

    def synthesize_script(self, script: str, output_path: str) -> float:
        """
        Synthesize a full script (newline-separated segments) to a single WAV file.
        Compatible with existing ShortVideoGenerator._synthesize_speech interface.
        Returns total duration.
        """
        segments = [s.strip() for s in script.split("\n") if s.strip()]
        wav_chunks: list[bytes] = []

        for seg_text in segments:
            if len(seg_text) > 1000:
                seg_text = seg_text[:1000]
            try:
                wav_chunks.append(self.synthesize(seg_text))
            except Exception as e:
                logger.error("Failed to synthesize segment: %s", e)

        if not wav_chunks:
            raise RuntimeError("No audio segments were synthesized")

        # Concatenate WAV chunks
        all_frames = b""
        params = None
        for chunk in wav_chunks:
            with wave.open(io.BytesIO(chunk), "rb") as wf:
                if params is None:
                    params = wf.getparams()
                all_frames += wf.readframes(wf.getnframes())

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with wave.open(output_path, "wb") as out:
            out.setparams(params)
            out.writeframes(all_frames)

        return get_wav_duration(all_frames if params is None else open(output_path, "rb").read())
