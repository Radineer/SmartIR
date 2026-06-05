"""
ショート動画生成サービス

IR分析結果からYouTube Shorts / TikTok向け縦型動画（9:16, 1080x1920）を生成する。

パイプライン:
1. Claude でハイライト / サマリースクリプト生成
2. AivisSpeech/Voicevox TTS で音声合成
3. SubtitleGenerator で字幕 (.ass) 生成
4. ffmpeg でビデオアセンブリ（グラデーション背景 + テキスト + キャラ + 字幕）
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
import wave
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from app.services.tts_service import TTSService

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TTS_ENGINE = os.getenv("TTS_ENGINE", "aivisspeech")
VOICEVOX_HOST = os.getenv("VOICEVOX_HOST", "http://localhost:50021")
AIVISSPEECH_HOST = os.getenv("AIVISSPEECH_HOST", "http://localhost:10101")
DEFAULT_SPEAKER_ID = int(os.getenv(
    "TTS_SPEAKER_ID",
    "1878365376" if TTS_ENGINE == "aivisspeech" else "3",
))

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FPS = 30

OUTPUT_DIR = Path(os.getenv("SHORT_VIDEO_OUTPUT_DIR", "./static/shorts"))

# Background gradient colors
BG_COLOR_TOP = "#1a1a2e"
BG_COLOR_BOTTOM = "#16213e"

FFMPEG_BIN = os.getenv("FFMPEG_PATH", "/opt/homebrew/Cellar/ffmpeg/8.1/bin/ffmpeg")

# Iris character prompt (same as run_auto_stream.py)
IRIS_SYSTEM_PROMPT = """あなたはVTuber向けの台本作家です。
キャラクター「イリス」の設定:
- 2050年から来たAIアナリスト（外見18歳、実年齢3歳）
- 金融特化型汎用AIとして東京証券取引所で開発された
- 普段は天然ボケで愛嬌がある。時々処理落ちでフリーズする
- 分析モードに入ると冷静沈着で的確
- チョコレートが大好き（味覚センサーのバグ）
- 口癖:「データは嘘をつきませんから」
- 最後に必ず免責表現を入れる:「イリスの分析は参考情報です。投資判断はご自身の責任でお願いします。」
"""


def _get_tts_host() -> str:
    if TTS_ENGINE == "aivisspeech":
        return AIVISSPEECH_HOST
    return VOICEVOX_HOST


def _get_wav_duration(path: str) -> float:
    """WAVファイルの再生時間（秒）を返す"""
    with wave.open(path, "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return frames / rate if rate else 0.0


def _escape_drawtext(text: str) -> str:
    """ffmpeg drawtext フィルター用にテキストをエスケープする"""
    # ffmpeg drawtext requires escaping of : ' \ and sometimes ;
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "'\\''")
    text = text.replace(":", "\\:")
    text = text.replace(";", "\\;")
    return text


# ---------------------------------------------------------------------------
# ShortVideoGenerator
# ---------------------------------------------------------------------------

class ShortVideoGenerator:
    """IR分析からショート動画を生成するジェネレーター"""

    def __init__(
        self,
        speaker_id: int | None = None,
        output_dir: str | Path | None = None,
        character_image: str | None = None,
        tts_service: TTSService | None = None,
    ):
        self.speaker_id = speaker_id or DEFAULT_SPEAKER_ID
        self.output_dir = Path(output_dir) if output_dir else OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.character_image = character_image  # Path to Iris PNG overlay
        self.tts = tts_service or TTSService()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        analysis: dict,
        output_path: str | None = None,
        style: str = "highlight",
        max_duration: int = 45,
    ) -> dict:
        """
        IR分析からショート動画を生成する。

        Args:
            analysis: IR分析辞書 (company_name, ticker_code, summary, key_points, sentiment)
            output_path: 出力ファイルパス（省略時は自動生成）
            style: "highlight" (キーポイント) or "summary" (全体要約)
            max_duration: 最大秒数

        Returns:
            {"video_path": str, "duration": float, "title": str,
             "description": str, "hashtags": list[str]}
        """
        company_name = analysis.get("company_name", "不明")
        ticker_code = analysis.get("ticker_code", "0000")
        now = datetime.now(JST)

        logger.info(f"Generating short video: {company_name} ({ticker_code}) style={style}")

        # 1. スクリプト生成
        script = self.generate_highlight_script(analysis, max_seconds=max_duration)
        logger.info(f"Script generated: {len(script)} chars")

        # 2. TTS 音声合成
        with tempfile.TemporaryDirectory(prefix="shortvideo_") as tmpdir:
            audio_path = os.path.join(tmpdir, "narration.wav")
            self.tts.synthesize_script(script, audio_path)
            audio_duration = _get_wav_duration(audio_path)
            logger.info(f"Audio synthesized: {audio_duration:.1f}s")

            # 3. 字幕生成
            subtitle_path = os.path.join(tmpdir, "subtitles.ass")
            self._generate_subtitles(script, audio_duration, subtitle_path)

            # 4. メタデータ生成
            title = self._generate_title(analysis, style)
            description = self._generate_description(analysis)
            hashtags = self._generate_hashtags(analysis)

            # 5. 出力パス決定
            if output_path is None:
                timestamp = now.strftime("%Y%m%d_%H%M%S")
                filename = f"short_{ticker_code}_{style}_{timestamp}.mp4"
                output_path = str(self.output_dir / filename)

            # 6. ffmpeg ビデオアセンブリ
            self.assemble_video(
                audio_path=audio_path,
                subtitle_path=subtitle_path,
                title=title,
                output_path=output_path,
                character_image=self.character_image,
                company_name=company_name,
                ticker_code=ticker_code,
                sentiment=analysis.get("sentiment", {}),
                duration=audio_duration,
            )

        logger.info(f"Short video saved: {output_path}")

        # 7. サムネイル自動生成
        thumbnail_path = None
        try:
            from app.services.thumbnail_generator import ThumbnailGenerator

            thumb_gen = ThumbnailGenerator()

            # センチメント判定
            sent = analysis.get("sentiment", {})
            if isinstance(sent, str):
                sent = json.loads(sent)
            sentiment_label = None
            pos_v = sent.get("positive") if isinstance(sent, dict) else None
            neg_v = sent.get("negative") if isinstance(sent, dict) else None
            if pos_v is not None and neg_v is not None:
                try:
                    sentiment_label = (
                        "positive" if float(pos_v) > float(neg_v)
                        else "negative" if float(neg_v) > float(pos_v)
                        else "neutral"
                    )
                except (ValueError, TypeError):
                    pass

            thumb_output = Path(output_path).with_suffix(".thumb.png")
            thumbnail_path = thumb_gen.generate(
                title=title,
                style="ir_analysis",
                company_name=company_name,
                ticker_code=ticker_code,
                sentiment=sentiment_label,
                date_str=now.strftime("%Y/%m/%d"),
                output_path=str(thumb_output),
            )
            logger.info(f"Short video thumbnail generated: {thumbnail_path}")
        except Exception as e:
            logger.warning(f"Thumbnail generation failed (non-fatal): {e}")

        return {
            "video_path": output_path,
            "duration": audio_duration,
            "title": title,
            "description": description,
            "hashtags": hashtags,
            "thumbnail_path": thumbnail_path,
        }

    def generate_highlight_script(
        self, analysis: dict, max_seconds: int = 45
    ) -> str:
        """Claudeを使ってIR分析からショート動画用のスクリプトを生成する"""
        import anthropic

        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        company_name = analysis.get("company_name", "不明")
        ticker_code = analysis.get("ticker_code", "不明")
        summary = analysis.get("summary", "")
        key_points = analysis.get("key_points", [])
        if isinstance(key_points, str):
            key_points = json.loads(key_points)
        sentiment = analysis.get("sentiment", {})
        if isinstance(sentiment, str):
            sentiment = json.loads(sentiment)

        # 日本語約5文字/秒 → max_seconds * 5 = 最大文字数目安
        max_chars = max_seconds * 5

        prompt = f"""以下のIR分析データを元に、YouTube Shorts / TikTok 向けのショート動画ナレーション台本を作成してください。

企業: {company_name} ({ticker_code})
要約: {summary}
重要ポイント: {', '.join(key_points) if key_points else '情報なし'}
センチメント: ポジティブ={sentiment.get('positive', 'N/A')}, ネガティブ={sentiment.get('negative', 'N/A')}

要件:
- {max_seconds}秒以内（約{max_chars}文字以内）で読める長さ
- 冒頭3秒で視聴者の注意を引くフック（驚きの数字やインパクトのある一言）
- 要点を3つ以内に絞る
- 最後に免責表現を含める
- ナレーションテキストのみ出力（演出指示やメタ説明は不要）
- 句読点を適切に入れてリズムを作る
- 改行で文を区切る（字幕の区切りに使う）
"""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=IRIS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )

        return response.content[0].text.strip()

    def assemble_video(
        self,
        audio_path: str,
        subtitle_path: str,
        title: str,
        output_path: str,
        character_image: str | None = None,
        company_name: str = "",
        ticker_code: str = "",
        sentiment: dict | None = None,
        duration: float | None = None,
    ) -> str:
        """
        ffmpegで縦型ビデオをアセンブルする。

        構成:
        - 背景: ダークグラデーション (#1a1a2e → #16213e)
        - タイトルテキスト (上部, 白, 影付き)
        - 企業名 / ティッカー (タイトル下)
        - センチメントインジケーター (緑/赤矢印 + パーセンテージ)
        - 字幕テキスト (中央下部, 黄色, ダーク背景)
        - キャラクター画像オーバーレイ (右下, オプション)
        """
        if duration is None:
            duration = _get_wav_duration(audio_path)

        sentiment = sentiment or {}
        pos = sentiment.get("positive")
        neg = sentiment.get("negative")

        # センチメント表示テキスト
        if pos is not None and neg is not None:
            try:
                pos_val = float(pos) * 100
                neg_val = float(neg) * 100
                if pos_val >= neg_val:
                    sentiment_text = f"▲ ポジティブ {pos_val:.0f}%"
                    sentiment_color = "0x00E676"
                else:
                    sentiment_text = f"▼ ネガティブ {neg_val:.0f}%"
                    sentiment_color = "0xFF5252"
            except (ValueError, TypeError):
                sentiment_text = ""
                sentiment_color = "0xFFFFFF"
        else:
            sentiment_text = ""
            sentiment_color = "0xFFFFFF"

        # ffmpeg フィルター構築
        # 1) グラデーション背景生成
        filters = []
        # lavfi で背景グラデーション生成
        bg_filter = (
            f"color=c={BG_COLOR_BOTTOM}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:d={duration}:r={FPS}[bg_base];"
            f"color=c={BG_COLOR_TOP}:s={VIDEO_WIDTH}x{int(VIDEO_HEIGHT / 2)}:d={duration}:r={FPS}[bg_top];"
            f"[bg_top]format=yuva420p,fade=t=out:st=0:d=0.001:alpha=0[bg_top_a];"
            f"[bg_base][bg_top_a]overlay=0:0[bg]"
        )
        filters.append(bg_filter)

        # 2) タイトルテキスト描画
        title_escaped = _escape_drawtext(title)
        title_filter = (
            f"[bg]drawtext="
            f"text='{title_escaped}':"
            f"fontsize=52:fontcolor=white:"
            f"shadowcolor=black:shadowx=3:shadowy=3:"
            f"x=(w-text_w)/2:y=180:"
            f"fontfile=/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
            f"[with_title]"
        )
        filters.append(title_filter)

        # 3) 企業名 + ティッカー
        if company_name:
            company_escaped = _escape_drawtext(f"{company_name}  ({ticker_code})")
            company_filter = (
                f"[with_title]drawtext="
                f"text='{company_escaped}':"
                f"fontsize=36:fontcolor=0xB0BEC5:"
                f"x=(w-text_w)/2:y=260:"
                f"fontfile=/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"
                f"[with_company]"
            )
            filters.append(company_filter)
            current_label = "with_company"
        else:
            current_label = "with_title"

        # 4) センチメントインジケーター
        if sentiment_text:
            sent_escaped = _escape_drawtext(sentiment_text)
            sent_filter = (
                f"[{current_label}]drawtext="
                f"text='{sent_escaped}':"
                f"fontsize=44:fontcolor={sentiment_color}:"
                f"shadowcolor=black:shadowx=2:shadowy=2:"
                f"x=(w-text_w)/2:y=340:"
                f"fontfile=/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
                f"[with_sentiment]"
            )
            filters.append(sent_filter)
            current_label = "with_sentiment"

        # 5) 免責テキスト（下部）
        disclaimer_escaped = _escape_drawtext("※投資判断はご自身の責任で")
        disclaimer_filter = (
            f"[{current_label}]drawtext="
            f"text='{disclaimer_escaped}':"
            f"fontsize=22:fontcolor=0x757575:"
            f"x=(w-text_w)/2:y=h-80:"
            f"fontfile=/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"
            f"[with_disclaimer]"
        )
        filters.append(disclaimer_filter)
        current_label = "with_disclaimer"

        # 6) キャラクター画像オーバーレイ
        input_args = []
        if character_image and os.path.isfile(character_image):
            input_args.extend(["-i", character_image])
            char_filter = (
                f"[1:v]scale=300:-1[char_scaled];"
                f"[{current_label}][char_scaled]overlay="
                f"x=W-w-40:y=H-h-120"
                f"[with_char]"
            )
            filters.append(char_filter)
            current_label = "with_char"

        # Copy subtitle to simple path to avoid ffmpeg ass filter escaping issues
        import shutil
        _simple_sub = "/tmp/_smartir_sub.ass"
        shutil.copy2(subtitle_path, _simple_sub)
        sub_filter = f"[{current_label}]ass=filename='/tmp/_smartir_sub.ass'[vout]"
        filters.append(sub_filter)

        filter_complex = ";".join(filters)

        # ffmpeg コマンド構築
        cmd = [
            FFMPEG_BIN, "-y",
            "-i", audio_path,
            *input_args,
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "0:a",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            "-r", str(FPS),
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-t", str(duration),
            output_path,
        ]

        logger.info(f"Running ffmpeg: {' '.join(cmd[:6])}...")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            logger.error(f"ffmpeg failed:\nstdout: {result.stdout}\nstderr: {result.stderr}")
            raise RuntimeError(f"ffmpeg failed with exit code {result.returncode}: {result.stderr[-500:]}")

        logger.info(f"Video assembled: {output_path}")
        return output_path

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _synthesize_speech(self, script: str, output_path: str) -> None:
        """AivisSpeech/Voicevox TTS で音声合成する"""
        tts_host = _get_tts_host()

        # スクリプトを改行で分割してセグメントごとに合成し結合
        segments = [s.strip() for s in script.split("\n") if s.strip()]

        wav_chunks: list[bytes] = []

        with httpx.Client(timeout=60.0) as client:
            for i, segment in enumerate(segments):
                if len(segment) > 1000:
                    segment = segment[:1000]

                for attempt in range(3):
                    try:
                        # audio_query
                        query_resp = client.post(
                            f"{tts_host}/audio_query",
                            params={"text": segment, "speaker": self.speaker_id},
                        )
                        if query_resp.status_code != 200:
                            logger.warning(
                                f"audio_query failed (attempt {attempt + 1}): {query_resp.text}"
                            )
                            continue

                        audio_query = query_resp.json()

                        # スピードを少し速める（ショート動画向け）
                        audio_query["speedScale"] = 1.15

                        # synthesis
                        synth_resp = client.post(
                            f"{tts_host}/synthesis",
                            params={"speaker": self.speaker_id},
                            json=audio_query,
                        )
                        if synth_resp.status_code != 200:
                            logger.warning(
                                f"synthesis failed (attempt {attempt + 1}): {synth_resp.text}"
                            )
                            continue

                        wav_chunks.append(synth_resp.content)
                        break

                    except httpx.TimeoutException:
                        logger.warning(f"TTS timeout (attempt {attempt + 1}) for segment {i}")
                        continue
                else:
                    logger.error(f"Failed to synthesize segment {i} after 3 attempts, skipping")

        if not wav_chunks:
            raise RuntimeError("No audio segments were synthesized")

        # WAVチャンクを結合
        self._concat_wav(wav_chunks, output_path)

    def _concat_wav(self, wav_chunks: list[bytes], output_path: str) -> None:
        """複数のWAVデータを結合して一つのWAVファイルに書き出す"""
        import io

        all_frames = b""
        params = None

        for chunk in wav_chunks:
            with wave.open(io.BytesIO(chunk), "rb") as wf:
                if params is None:
                    params = wf.getparams()
                all_frames += wf.readframes(wf.getnframes())

        if params is None:
            raise RuntimeError("No valid WAV data to concatenate")

        with wave.open(output_path, "wb") as out:
            out.setparams(params)
            out.writeframes(all_frames)

    def _generate_subtitles(
        self, script: str, duration: float, output_path: str
    ) -> None:
        """
        スクリプトからASS字幕ファイルを生成する。

        SubtitleGenerator が利用可能ならそちらを使い、
        なければシンプルなタイムスタンプ分割で生成する。
        """
        try:
            from app.services.subtitle_generator import SubtitleGenerator

            generator = SubtitleGenerator()
            generator.generate(
                text=script,
                duration=duration,
                output_path=output_path,
                style="short_video",
            )
            logger.info("Subtitles generated via SubtitleGenerator")
            return
        except (ImportError, Exception) as e:
            logger.info(f"SubtitleGenerator not available ({e}), using fallback")

        # フォールバック: 改行ベースの均等分割ASS生成
        lines = [s.strip() for s in script.split("\n") if s.strip()]
        if not lines:
            lines = [""]

        time_per_line = duration / len(lines)

        ass_content = self._build_ass_header()
        ass_content += "\n[Events]\n"
        ass_content += "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"

        for i, line in enumerate(lines):
            start = i * time_per_line
            end = (i + 1) * time_per_line
            start_ts = self._seconds_to_ass_time(start)
            end_ts = self._seconds_to_ass_time(end)
            # 長い行は40文字で折り返し
            wrapped = self._wrap_text(line, max_width=20)
            ass_content += (
                f"Dialogue: 0,{start_ts},{end_ts},Subtitle,,0,0,0,,{wrapped}\n"
            )

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(ass_content)

    def _build_ass_header(self) -> str:
        """ASS字幕ファイルのヘッダーを生成（縦型動画向けスタイル）"""
        return f"""[Script Info]
Title: SmartIR Short Video Subtitles
ScriptType: v4.00+
PlayResX: {VIDEO_WIDTH}
PlayResY: {VIDEO_HEIGHT}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Subtitle,Hiragino Sans,56,&H00FFFF00,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,3,3,0,2,40,40,350,1
"""

    @staticmethod
    def _seconds_to_ass_time(seconds: float) -> str:
        """秒をASS時刻形式 (H:MM:SS.CC) に変換"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int((seconds % 1) * 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    @staticmethod
    def _wrap_text(text: str, max_width: int = 20) -> str:
        """テキストを指定幅で折り返す（ASS改行 \\N 使用）"""
        if len(text) <= max_width:
            return text
        parts = []
        while text:
            parts.append(text[:max_width])
            text = text[max_width:]
        return "\\N".join(parts)

    def _generate_title(self, analysis: dict, style: str) -> str:
        """動画タイトルを生成"""
        company = analysis.get("company_name", "")
        ticker = analysis.get("ticker_code", "")
        sentiment = analysis.get("sentiment", {})

        if isinstance(sentiment, str):
            sentiment = json.loads(sentiment)

        pos = sentiment.get("positive")
        neg = sentiment.get("negative")

        try:
            pos_val = float(pos) * 100 if pos else 0
            neg_val = float(neg) * 100 if neg else 0
        except (ValueError, TypeError):
            pos_val, neg_val = 0, 0

        if pos_val > neg_val:
            emoji = "📈"
            tone = "ポジティブ"
        else:
            emoji = "📉"
            tone = "注意"

        if style == "highlight":
            return f"{emoji} {company}({ticker}) IR速報 {tone}シグナル！"
        return f"{emoji} {company}({ticker}) IR分析まとめ"

    def _generate_description(self, analysis: dict) -> str:
        """動画の説明文を生成"""
        company = analysis.get("company_name", "")
        ticker = analysis.get("ticker_code", "")
        summary = analysis.get("summary", "")
        now = datetime.now(JST)

        return (
            f"{company}({ticker})の最新IR分析をAIアナリスト・イリスが解説！\n\n"
            f"{summary[:200]}\n\n"
            f"📅 {now.strftime('%Y年%m月%d日')}\n"
            f"🤖 AI分析 by SmartIR\n\n"
            f"⚠️ 本動画は情報提供を目的としており、投資助言ではありません。"
            f"投資判断はご自身の責任でお願いします。"
        )

    def _generate_hashtags(self, analysis: dict) -> list[str]:
        """SNS向けハッシュタグを生成"""
        company = analysis.get("company_name", "")
        ticker = analysis.get("ticker_code", "")

        tags = [
            "#株式投資",
            "#IR分析",
            "#決算",
            f"#{company}" if company else "",
            f"#{ticker}" if ticker else "",
            "#投資",
            "#AI分析",
            "#SmartIR",
            "#株",
            "#日本株",
        ]
        return [t for t in tags if t]
