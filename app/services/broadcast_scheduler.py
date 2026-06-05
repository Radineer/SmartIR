from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from typing import Dict, Any, Optional, Callable
from pathlib import Path
from zoneinfo import ZoneInfo
import logging
import asyncio
import json
import os
import uuid
import shutil
import subprocess
import tempfile

import httpx

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

# TTS configuration (mirrors video_studio.py)
TTS_ENGINE = os.getenv("TTS_ENGINE", "aivisspeech")
VOICEVOX_HOST = os.getenv("VOICEVOX_HOST", "http://localhost:50021")
AIVISSPEECH_HOST = os.getenv("AIVISSPEECH_HOST", "http://localhost:10101")
DEFAULT_SPEAKER_ID = int(os.getenv(
    "TTS_SPEAKER_ID",
    "1878365376" if TTS_ENGINE == "aivisspeech" else "3",
))

AUDIO_OUTPUT_DIR = Path(os.getenv("AUDIO_OUTPUT_DIR", "./static/audio"))
VIDEO_OUTPUT_DIR = Path(os.getenv("VIDEO_OUTPUT_DIR", "./static/videos"))


def _get_tts_host() -> str:
    """Get the TTS engine host URL based on configuration."""
    if TTS_ENGINE == "aivisspeech":
        return AIVISSPEECH_HOST
    return VOICEVOX_HOST


# ---------------------------------------------------------------------------
# DB helpers (same pattern as scripts/run_auto_stream.py)
# ---------------------------------------------------------------------------

def _get_db_connection():
    """Supabase PostgreSQL 接続を取得"""
    import psycopg2

    db_url = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL or SUPABASE_DB_URL not set")
    return psycopg2.connect(db_url)


def _fetch_latest_analyses(limit: int = 5) -> list[dict]:
    """最新の IR 分析結果を取得"""
    conn = _get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    ar.id,
                    ar.summary,
                    ar.key_points,
                    ar.sentiment_positive,
                    ar.sentiment_negative,
                    ar.sentiment_neutral,
                    ar.created_at,
                    c.name AS company_name,
                    c.ticker_code
                FROM analysis_results ar
                JOIN documents d ON ar.document_id = d.id
                JOIN companies c ON d.company_id = c.id
                ORDER BY ar.created_at DESC
                LIMIT %s
            """, (limit,))
            columns = [desc[0] for desc in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]
            for row in rows:
                row["sentiment"] = {
                    "positive": row.pop("sentiment_positive", None),
                    "negative": row.pop("sentiment_negative", None),
                    "neutral": row.pop("sentiment_neutral", None),
                }
            return rows
    finally:
        conn.close()


def _fetch_weekly_analyses(limit: int = 20) -> list[dict]:
    """過去 7 日間の IR 分析結果を取得"""
    conn = _get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    ar.id,
                    ar.summary,
                    ar.key_points,
                    ar.sentiment_positive,
                    ar.sentiment_negative,
                    ar.sentiment_neutral,
                    ar.created_at,
                    c.name AS company_name,
                    c.ticker_code
                FROM analysis_results ar
                JOIN documents d ON ar.document_id = d.id
                JOIN companies c ON d.company_id = c.id
                WHERE ar.created_at >= NOW() - INTERVAL '7 days'
                ORDER BY ar.created_at DESC
                LIMIT %s
            """, (limit,))
            columns = [desc[0] for desc in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]
            for row in rows:
                row["sentiment"] = {
                    "positive": row.pop("sentiment_positive", None),
                    "negative": row.pop("sentiment_negative", None),
                    "neutral": row.pop("sentiment_neutral", None),
                }
            return rows
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Script generation (same pattern as scripts/run_auto_stream.py)
# ---------------------------------------------------------------------------

_IRIS_SYSTEM_PROMPT = """あなたはVTuber向けの台本作家です。
キャラクター「イリス」の設定:
- 2050年から来たAIアナリスト（外見18歳、実年齢3歳）
- 金融特化型汎用AIとして東京証券取引所で開発された
- 普段は天然ボケで愛嬌がある。時々処理落ちでフリーズする
- 分析モードに入ると冷静沈着で的確
- チョコレートが大好き（味覚センサーのバグ）
- 口癖:「データは嘘をつきませんから」
- 最後に必ず免責表現を入れる:「イリスの分析は参考情報です。投資判断はご自身の責任でお願いします。」
"""


def _generate_script(
    stream_type: str,
    analyses: list[dict],
    duration_minutes: int,
) -> str:
    """Anthropic Claude で配信台本を生成（OpenAI フォールバック）"""
    import anthropic

    now = datetime.now(JST)
    date_str = now.strftime("%Y年%m月%d日")
    weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
    weekday = weekday_names[now.weekday()]

    analyses_text = ""
    for a in analyses:
        key_points = a.get("key_points", [])
        if isinstance(key_points, str):
            key_points = json.loads(key_points)
        sentiment = a.get("sentiment", {})
        if isinstance(sentiment, str):
            sentiment = json.loads(sentiment)

        analyses_text += (
            f"\n企業: {a.get('company_name', '不明')} ({a.get('ticker_code', '不明')})\n"
            f"要約: {a.get('summary', '情報なし')}\n"
            f"重要ポイント: {', '.join(key_points) if key_points else '情報なし'}\n"
            f"センチメント: ポジティブ={sentiment.get('positive', 'N/A')}, "
            f"ネガティブ={sentiment.get('negative', 'N/A')}\n"
        )

    prompts = {
        "morning_market": (
            f"本日: {date_str}（{weekday}曜日）\n\n"
            f"以下の最新IR分析データを元に、イリスが{duration_minutes}分程度で話せる"
            f"朝の市況サマリー台本を作成してください。\n{analyses_text}\n\n"
            "台本の形式:\n1. 朝の挨拶と日付の紹介（元気よく）\n2. 最新IR情報のハイライト\n"
            "3. 注目すべきポイント\n4. 視聴者への呼びかけ\n5. 締めの挨拶と免責表現\n\n"
            "注意:\n- 朝らしい爽やかな雰囲気で\n- 専門用語は分かりやすく言い換え\n"
            "- 時代ギャップネタを1つ入れる\n- 台本のみ出力（メタ説明や注釈は不要）"
        ),
        "weekly_summary": (
            f"本日: {date_str}（{weekday}曜日）\n\n"
            f"以下の今週のIR分析を元に、イリスが{duration_minutes}分程度で話せる"
            f"週間まとめ台本を作成してください。\n{analyses_text}\n\n"
            "台本の形式:\n1. 挨拶と週間レビューの導入\n2. 今週の主要IR発表まとめ\n"
            "3. 各企業のハイライト\n4. セクター別の傾向（分析モードで）\n"
            "5. 来週の展望と注目ポイント\n6. 締めの挨拶と免責表現\n\n"
            "注意:\n- 複数企業を比較する視点\n- 好決算は喜び、不振は励ます感情表現\n"
            "- 分析モードへの切り替わりを含める\n- 台本のみ出力（メタ説明や注釈は不要）"
        ),
    }

    prompt = prompts.get(stream_type, prompts["morning_market"])

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=_IRIS_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response.content[0].text


# ---------------------------------------------------------------------------
# TTS audio generation (same pattern as video_studio.py audio_query+synthesis)
# ---------------------------------------------------------------------------

async def _generate_tts_audio(
    script_text: str,
    output_path: Path,
    speaker_id: int = DEFAULT_SPEAKER_ID,
) -> float:
    """
    台本テキストから TTS 音声を生成し WAV ファイルに保存する。

    Returns:
        float: 音声の長さ（秒）
    """
    import io
    import wave
    import struct

    tts_host = _get_tts_host()

    # 台本をセグメント分割（句点区切り、2-3 文ずつ）
    import re
    sentences = re.split(r'(?<=[。！？])', script_text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    segments: list[str] = []
    group: list[str] = []
    for sentence in sentences:
        group.append(sentence)
        if len(group) >= 2:
            segments.append("".join(group))
            group = []
    if group:
        segments.append("".join(group))

    audio_chunks: list[bytes] = []

    async with httpx.AsyncClient(timeout=60.0) as client:
        for i, text in enumerate(segments):
            if not text.strip():
                continue

            for attempt in range(3):
                try:
                    # audio_query
                    query_resp = await client.post(
                        f"{tts_host}/audio_query",
                        params={"text": text[:1000], "speaker": speaker_id},
                    )
                    if query_resp.status_code != 200:
                        logger.warning(
                            f"TTS audio_query failed (attempt {attempt + 1}): "
                            f"{query_resp.status_code}"
                        )
                        continue

                    audio_query = query_resp.json()

                    # synthesis
                    synth_resp = await client.post(
                        f"{tts_host}/synthesis",
                        params={"speaker": speaker_id},
                        json=audio_query,
                    )
                    if synth_resp.status_code != 200:
                        logger.warning(
                            f"TTS synthesis failed (attempt {attempt + 1}): "
                            f"{synth_resp.status_code}"
                        )
                        continue

                    audio_chunks.append(synth_resp.content)
                    logger.debug(f"TTS segment {i + 1}/{len(segments)} generated")
                    break

                except httpx.TimeoutException:
                    logger.warning(f"TTS timeout on segment {i + 1} (attempt {attempt + 1})")
                except Exception as e:
                    logger.warning(f"TTS error on segment {i + 1} (attempt {attempt + 1}): {e}")

    if not audio_chunks:
        raise RuntimeError("TTS generation failed: no audio chunks produced")

    # WAV チャンクを結合
    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined_samples: list[int] = []
    sample_rate = 24000
    sample_width = 2

    for chunk in audio_chunks:
        try:
            with wave.open(io.BytesIO(chunk), "rb") as wf:
                sample_rate = wf.getframerate()
                sample_width = wf.getsampwidth()
                n_frames = wf.getnframes()
                raw = wf.readframes(n_frames)
                fmt = f"<{n_frames}h" if sample_width == 2 else f"<{n_frames}b"
                combined_samples.extend(struct.unpack(fmt, raw))
        except Exception as e:
            logger.warning(f"Failed to parse WAV chunk: {e}")

    if not combined_samples:
        raise RuntimeError("TTS generation failed: could not parse any WAV data")

    with wave.open(str(output_path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(sample_width)
        out.setframerate(sample_rate)
        fmt = f"<{len(combined_samples)}h" if sample_width == 2 else f"<{len(combined_samples)}b"
        out.writeframes(struct.pack(fmt, *combined_samples))

    duration = len(combined_samples) / sample_rate
    logger.info(f"TTS audio saved: {output_path} ({duration:.1f}s)")
    return duration


# ---------------------------------------------------------------------------
# Video rendering (FFmpeg, same pattern as video_studio.py)
# ---------------------------------------------------------------------------

def _render_video_ffmpeg(
    audio_path: Path,
    output_path: Path,
    title: str,
    duration: float,
) -> Path:
    """FFmpeg で音声 + タイトルカード動画を生成する。"""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg not found. Please install FFmpeg.")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # キャラクター画像
    character_image = (
        Path(__file__).parent.parent.parent
        / "frontend" / "public" / "images" / "iris" / "iris-normal.png"
    )

    # タイトルをエスケープ
    safe_title = title.replace("'", "'\\''").replace(":", "\\:")[:100]

    filters = [
        (
            f"drawtext=text='{safe_title}'"
            f":fontcolor=white:fontsize=48"
            f":x=(w-text_w)/2:y=60"
            f":shadowcolor=black:shadowx=2:shadowy=2"
        ),
    ]

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c=1e1b4b:s=1920x1080:d={duration}:r=30",
    ]

    if character_image.exists():
        cmd.extend(["-i", str(character_image)])
        overlay = "[0:v][1:v]overlay=W-w-50:H-h-20:format=auto"
        filter_complex = f"{overlay},{','.join(filters)}" if filters else overlay
        cmd.extend(["-filter_complex", filter_complex])
    else:
        if filters:
            cmd.extend(["-vf", ",".join(filters)])

    cmd.extend([
        "-i", str(audio_path),
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path),
    ])

    logger.info(f"Running FFmpeg render ({duration:.0f}s video)")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, shell=False)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {result.stderr[-500:]}")

    logger.info(f"Video rendered: {output_path}")
    return output_path


class BroadcastScheduler:
    """動画配信スケジューラー"""

    _instance = None

    def __new__(cls):
        """シングルトンパターン"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.scheduler = AsyncIOScheduler()
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self._initialized = True

    def start(self):
        """スケジューラーを開始"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Broadcast scheduler started")

    def shutdown(self):
        """スケジューラーを停止"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Broadcast scheduler stopped")

    def schedule_video_upload(
        self,
        job_id: str,
        video_path: str,
        title: str,
        description: str,
        publish_time: datetime,
        tags: list[str] = None,
        thumbnail_path: str = None,
    ) -> Dict[str, Any]:
        """
        動画アップロードをスケジュール

        Args:
            job_id: ジョブの一意識別子
            video_path: 動画ファイルのパス
            title: 動画タイトル
            description: 動画の説明
            publish_time: 公開予定時刻
            tags: タグのリスト
            thumbnail_path: サムネイル画像のパス

        Returns:
            Dict: ジョブ情報
        """
        from app.services.youtube_uploader import YouTubeUploader

        async def upload_job():
            try:
                logger.info(f"Starting scheduled upload: {job_id}")
                uploader = YouTubeUploader()
                uploader.authenticate_with_tokens()

                result = uploader.upload_video(
                    video_path=video_path,
                    title=title,
                    description=description,
                    tags=tags,
                    privacy_status="private",  # 予約投稿として非公開でアップロード
                )

                if thumbnail_path:
                    uploader.set_thumbnail(result["video_id"], thumbnail_path)

                self.jobs[job_id]["status"] = "completed"
                self.jobs[job_id]["result"] = result
                logger.info(f"Scheduled upload completed: {result['url']}")

            except Exception as e:
                self.jobs[job_id]["status"] = "failed"
                self.jobs[job_id]["error"] = str(e)
                logger.error(f"Scheduled upload failed: {str(e)}")

        self.scheduler.add_job(
            upload_job,
            trigger=DateTrigger(run_date=publish_time),
            id=job_id,
            replace_existing=True,
        )

        self.jobs[job_id] = {
            "status": "scheduled",
            "publish_time": publish_time,
            "video_path": video_path,
            "title": title,
            "created_at": datetime.now(),
        }

        logger.info(f"Video upload scheduled: {job_id} at {publish_time}")
        return self.jobs[job_id]

    def schedule_daily_analysis(
        self,
        hour: int = 20,
        minute: int = 0,
        callback: Callable = None,
    ) -> str:
        """
        毎日の自動配信をスケジュール

        Args:
            hour: 実行時間（時）
            minute: 実行時間（分）
            callback: カスタムコールバック関数

        Returns:
            str: ジョブID
        """
        job_id = "daily_analysis"

        if callback:
            job_func = callback
        else:
            job_func = self._daily_analysis_job

        self.scheduler.add_job(
            job_func,
            trigger=CronTrigger(hour=hour, minute=minute),
            id=job_id,
            replace_existing=True,
        )

        self.jobs[job_id] = {
            "status": "active",
            "schedule": f"{hour:02d}:{minute:02d} daily",
            "type": "recurring",
        }

        logger.info(f"Daily analysis scheduled at {hour:02d}:{minute:02d}")
        return job_id

    async def _daily_analysis_job(self):
        """
        日次分析動画生成・配信ジョブ

        実行フロー:
        1. 最新のIR分析結果を DB から取得
        2. AI（Anthropic Claude）で配信台本を生成
        3. TTS（AivisSpeech/Voicevox）で音声生成
        4. FFmpeg で動画レンダリング
        5. YouTube にアップロード
        """
        job_id = f"daily_{datetime.now(JST).strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"Starting daily analysis job: {job_id}")

        self.jobs.setdefault("daily_analysis", {})["last_run_id"] = job_id
        self.jobs["daily_analysis"]["last_run_status"] = "running"

        try:
            # ---- Phase 1: 最新 IR 分析結果を DB から取得 ----
            logger.info("[Phase 1] Fetching latest IR analyses from DB...")
            try:
                analyses = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: _fetch_latest_analyses(limit=5)
                )
            except Exception as e:
                logger.error(f"[Phase 1] DB fetch failed: {e}")
                raise

            if not analyses:
                logger.warning("[Phase 1] No analyses found, using placeholder")
                analyses = [{
                    "company_name": "テスト企業",
                    "ticker_code": "0000",
                    "summary": "本日のIR情報はまだ更新されていません。",
                    "key_points": ["データ更新待ち"],
                    "sentiment": {"positive": "N/A", "negative": "N/A"},
                }]

            logger.info(f"[Phase 1] Found {len(analyses)} analyses")

            # ---- Phase 2: AI 台本生成 ----
            logger.info("[Phase 2] Generating script with Anthropic Claude...")
            try:
                script_text = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: _generate_script(
                        stream_type="morning_market",
                        analyses=analyses,
                        duration_minutes=10,
                    ),
                )
            except Exception as e:
                logger.error(f"[Phase 2] Script generation failed: {e}")
                raise

            logger.info(f"[Phase 2] Script generated ({len(script_text)} chars)")

            # ---- Phase 3: TTS 音声生成 ----
            logger.info("[Phase 3] Generating TTS audio...")
            AUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            audio_filename = f"daily_{job_id}.wav"
            audio_path = AUDIO_OUTPUT_DIR / audio_filename

            try:
                audio_duration = await _generate_tts_audio(
                    script_text=script_text,
                    output_path=audio_path,
                )
            except Exception as e:
                logger.error(f"[Phase 3] TTS generation failed: {e}")
                raise

            logger.info(f"[Phase 3] Audio generated: {audio_path} ({audio_duration:.1f}s)")

            # ---- Phase 3.5: 字幕生成 (SRT / VTT) ----
            logger.info("[Phase 3.5] Generating subtitles from audio...")
            srt_path = audio_path.with_suffix(".srt")
            try:
                from app.services.subtitle_generator import SubtitleGenerator

                subtitle_gen = SubtitleGenerator(model_size="base", device="cpu")
                srt_file = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: subtitle_gen.from_audio(
                        audio_path=str(audio_path),
                        output_path=str(srt_path),
                        language="ja",
                    ),
                )
                vtt_file = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: subtitle_gen.srt_to_vtt(srt_file),
                )
                logger.info(f"[Phase 3.5] Subtitles generated: {srt_file}, {vtt_file}")
            except Exception as e:
                logger.warning(f"[Phase 3.5] Subtitle generation failed (non-fatal): {e}")

            # ---- Phase 3.7: BGM ミキシング ----
            logger.info("[Phase 3.7] Mixing BGM with narration...")
            mixed_audio_path = audio_path  # fallback: use raw narration
            try:
                from app.services.bgm_mixer import BGMMixer

                bgm_mixer = BGMMixer()
                bgm_track = bgm_mixer.select_track(
                    mood="calm", duration=audio_duration,
                )
                mixed_filename = f"mixed_daily_{job_id}.m4a"
                mixed_output = AUDIO_OUTPUT_DIR / mixed_filename
                mixed_audio_path = Path(
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: bgm_mixer.mix(
                            narration_path=str(audio_path),
                            bgm_path=bgm_track,
                            output_path=str(mixed_output),
                            bgm_volume=0.10,
                            duck_volume=0.05,
                            fade_in=2.0,
                            fade_out=3.0,
                        ),
                    )
                )
                logger.info(f"[Phase 3.7] BGM mixed: {mixed_audio_path}")
            except Exception as e:
                logger.warning(f"[Phase 3.7] BGM mixing failed (non-fatal): {e}")

            # ---- Phase 4: 動画レンダリング（Remotion優先、ffmpegフォールバック） ----
            VIDEO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            video_filename = f"daily_{job_id}.mp4"
            video_path = VIDEO_OUTPUT_DIR / video_filename

            now = datetime.now(JST)
            date_str = now.strftime("%Y/%m/%d")
            video_title = f"{date_str} 朝の市況サマリー｜イリスのIR分析"

            try:
                from app.services.remotion_renderer import RemotionRenderer, build_script_segments

                renderer = RemotionRenderer()
                if renderer.is_available():
                    logger.info("[Phase 4] Rendering video with Remotion (high quality)...")
                    segments = build_script_segments(
                        script_text=script_text,
                        analysis_data=analyses[0] if analyses else None,
                    )
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: renderer.render(
                            title=video_title,
                            script_segments=segments,
                            audio_path=str(mixed_audio_path),
                            output_path=str(video_path),
                        ),
                    )
                else:
                    raise RuntimeError("Remotion not available")
            except Exception as e:
                logger.warning(f"[Phase 4] Remotion failed ({e}), falling back to FFmpeg...")
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: _render_video_ffmpeg(
                        audio_path=mixed_audio_path,
                        output_path=video_path,
                        title=video_title,
                        duration=audio_duration,
                    ),
                )

            logger.info(f"[Phase 4] Video rendered: {video_path}")

            # ---- Phase 4.5: サムネイル生成 ----
            logger.info("[Phase 4.5] Generating thumbnail...")
            thumbnail_path = None
            try:
                from app.services.thumbnail_generator import ThumbnailGenerator

                thumb_gen = ThumbnailGenerator()

                # 先頭の分析からセンチメントを判定
                first = analyses[0] if analyses else {}
                s = first.get("sentiment", {})
                pos = s.get("positive") if isinstance(s, dict) else None
                neg = s.get("negative") if isinstance(s, dict) else None
                sentiment_label = None
                if pos is not None and neg is not None:
                    try:
                        pos_f, neg_f = float(pos), float(neg)
                        if pos_f > neg_f:
                            sentiment_label = "positive"
                        elif neg_f > pos_f:
                            sentiment_label = "negative"
                        else:
                            sentiment_label = "neutral"
                    except (ValueError, TypeError):
                        pass

                thumb_output = str(VIDEO_OUTPUT_DIR / f"thumb_{job_id}.png")
                thumbnail_path = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: thumb_gen.generate(
                        title=video_title,
                        style="morning_market",
                        company_name=first.get("company_name"),
                        ticker_code=first.get("ticker_code"),
                        sentiment=sentiment_label,
                        date_str=date_str,
                        output_path=thumb_output,
                    ),
                )
                logger.info(f"[Phase 4.5] Thumbnail generated: {thumbnail_path}")
            except Exception as e:
                logger.warning(f"[Phase 4.5] Thumbnail generation failed (non-fatal): {e}")

            # ---- Phase 5: YouTube アップロード ----
            logger.info("[Phase 5] Uploading to YouTube...")
            try:
                from app.services.youtube_uploader import YouTubeUploader

                uploader = YouTubeUploader()
                uploader.authenticate_with_tokens()

                # 動画説明文を構築
                company_names = ", ".join(
                    a.get("company_name", "") for a in analyses if a.get("company_name")
                )
                description = (
                    f"{date_str} 朝の市況サマリー\n\n"
                    f"取り上げた企業: {company_names}\n\n"
                    f"AIアナリスト「イリス」による最新IR分析です。\n"
                    f"※イリスの分析は参考情報です。投資判断はご自身の責任でお願いします。\n\n"
                    f"#IR分析 #株式投資 #AIVTuber #イリス"
                )

                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: uploader.upload_video(
                        video_path=str(video_path),
                        title=video_title,
                        description=description,
                        tags=["IR分析", "株式投資", "市況", "イリス", "AIVTuber", "朝の市況"],
                        category_id="22",
                        privacy_status="public",
                    ),
                )
                # サムネイル設定
                if thumbnail_path and result.get("video_id"):
                    try:
                        await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: uploader.set_thumbnail(
                                result["video_id"], thumbnail_path
                            ),
                        )
                        logger.info("[Phase 5] Thumbnail set on YouTube video")
                    except Exception as te:
                        logger.warning(f"[Phase 5] Thumbnail upload failed (non-fatal): {te}")

            except Exception as e:
                logger.error(f"[Phase 5] YouTube upload failed: {e}")
                raise

            logger.info(f"[Phase 5] Uploaded: {result.get('url', 'unknown')}")

            # ---- 完了 ----
            self.jobs["daily_analysis"]["last_run_status"] = "completed"
            self.jobs["daily_analysis"]["last_run_result"] = {
                "video_url": result.get("url"),
                "video_id": result.get("video_id"),
                "analyses_count": len(analyses),
                "audio_duration": audio_duration,
                "completed_at": datetime.now(JST).isoformat(),
            }
            logger.info(f"Daily analysis job completed: {result.get('url')}")

        except Exception as e:
            self.jobs["daily_analysis"]["last_run_status"] = "failed"
            self.jobs["daily_analysis"]["last_run_error"] = str(e)
            logger.error(f"Daily analysis job failed: {e}", exc_info=True)

    def schedule_weekly_summary(
        self,
        day_of_week: str = "sun",
        hour: int = 18,
        minute: int = 0,
    ) -> str:
        """
        週次サマリー配信をスケジュール

        Args:
            day_of_week: 曜日 (mon, tue, wed, thu, fri, sat, sun)
            hour: 実行時間（時）
            minute: 実行時間（分）

        Returns:
            str: ジョブID
        """
        job_id = "weekly_summary"

        self.scheduler.add_job(
            self._weekly_summary_job,
            trigger=CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute),
            id=job_id,
            replace_existing=True,
        )

        self.jobs[job_id] = {
            "status": "active",
            "schedule": f"{day_of_week} {hour:02d}:{minute:02d}",
            "type": "recurring",
        }

        logger.info(f"Weekly summary scheduled on {day_of_week} at {hour:02d}:{minute:02d}")
        return job_id

    async def _weekly_summary_job(self):
        """
        週次サマリー動画生成・配信ジョブ

        実行フロー:
        1. 過去 7 日間の IR 分析結果を DB から取得
        2. AI（Anthropic Claude）で週間まとめ台本を生成
        3. TTS（AivisSpeech/Voicevox）で音声生成
        4. FFmpeg で動画レンダリング
        5. YouTube にアップロード
        """
        job_id = f"weekly_{datetime.now(JST).strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"Starting weekly summary job: {job_id}")

        self.jobs.setdefault("weekly_summary", {})["last_run_id"] = job_id
        self.jobs["weekly_summary"]["last_run_status"] = "running"

        try:
            # ---- Phase 1: 過去 7 日間の IR 分析結果を DB から取得 ----
            logger.info("[Phase 1] Fetching weekly IR analyses from DB...")
            try:
                analyses = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: _fetch_weekly_analyses(limit=20)
                )
            except Exception as e:
                logger.error(f"[Phase 1] DB fetch failed: {e}")
                raise

            if not analyses:
                logger.warning("[Phase 1] No analyses found for the past week, using placeholder")
                analyses = [{
                    "company_name": "テスト企業",
                    "ticker_code": "0000",
                    "summary": "今週のIR情報はまだ更新されていません。",
                    "key_points": ["データ更新待ち"],
                    "sentiment": {"positive": "N/A", "negative": "N/A"},
                }]

            logger.info(f"[Phase 1] Found {len(analyses)} analyses from the past week")

            # ---- Phase 2: AI 台本生成 ----
            logger.info("[Phase 2] Generating weekly summary script with Anthropic Claude...")
            try:
                script_text = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: _generate_script(
                        stream_type="weekly_summary",
                        analyses=analyses,
                        duration_minutes=25,
                    ),
                )
            except Exception as e:
                logger.error(f"[Phase 2] Script generation failed: {e}")
                raise

            logger.info(f"[Phase 2] Script generated ({len(script_text)} chars)")

            # ---- Phase 3: TTS 音声生成 ----
            logger.info("[Phase 3] Generating TTS audio...")
            AUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            audio_filename = f"weekly_{job_id}.wav"
            audio_path = AUDIO_OUTPUT_DIR / audio_filename

            try:
                audio_duration = await _generate_tts_audio(
                    script_text=script_text,
                    output_path=audio_path,
                )
            except Exception as e:
                logger.error(f"[Phase 3] TTS generation failed: {e}")
                raise

            logger.info(f"[Phase 3] Audio generated: {audio_path} ({audio_duration:.1f}s)")

            # ---- Phase 3.5: 字幕生成 (SRT / VTT) ----
            logger.info("[Phase 3.5] Generating subtitles from audio...")
            srt_path = audio_path.with_suffix(".srt")
            try:
                from app.services.subtitle_generator import SubtitleGenerator

                subtitle_gen = SubtitleGenerator(model_size="base", device="cpu")
                srt_file = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: subtitle_gen.from_audio(
                        audio_path=str(audio_path),
                        output_path=str(srt_path),
                        language="ja",
                    ),
                )
                vtt_file = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: subtitle_gen.srt_to_vtt(srt_file),
                )
                logger.info(f"[Phase 3.5] Subtitles generated: {srt_file}, {vtt_file}")
            except Exception as e:
                logger.warning(f"[Phase 3.5] Subtitle generation failed (non-fatal): {e}")

            # ---- Phase 3.7: BGM ミキシング ----
            logger.info("[Phase 3.7] Mixing BGM with narration...")
            mixed_audio_path = audio_path  # fallback: use raw narration
            try:
                from app.services.bgm_mixer import BGMMixer

                bgm_mixer = BGMMixer()
                bgm_track = bgm_mixer.select_track(
                    mood="serious", duration=audio_duration,
                )
                mixed_filename = f"mixed_weekly_{job_id}.m4a"
                mixed_output = AUDIO_OUTPUT_DIR / mixed_filename
                mixed_audio_path = Path(
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: bgm_mixer.mix(
                            narration_path=str(audio_path),
                            bgm_path=bgm_track,
                            output_path=str(mixed_output),
                            bgm_volume=0.10,
                            duck_volume=0.05,
                            fade_in=2.0,
                            fade_out=3.0,
                        ),
                    )
                )
                logger.info(f"[Phase 3.7] BGM mixed: {mixed_audio_path}")
            except Exception as e:
                logger.warning(f"[Phase 3.7] BGM mixing failed (non-fatal): {e}")

            # ---- Phase 4: 動画レンダリング（Remotion優先、ffmpegフォールバック） ----
            VIDEO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            video_filename = f"weekly_{job_id}.mp4"
            video_path = VIDEO_OUTPUT_DIR / video_filename

            now = datetime.now(JST)
            date_str = now.strftime("%Y/%m/%d")
            video_title = f"{date_str} 週間マーケットまとめ｜イリスのIR分析"

            try:
                from app.services.remotion_renderer import RemotionRenderer, build_script_segments

                renderer = RemotionRenderer()
                if renderer.is_available():
                    logger.info("[Phase 4] Rendering video with Remotion (high quality)...")
                    segments = build_script_segments(
                        script_text=script_text,
                        analysis_data=analyses[0] if analyses else None,
                    )
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: renderer.render(
                            title=video_title,
                            script_segments=segments,
                            audio_path=str(mixed_audio_path),
                            output_path=str(video_path),
                        ),
                    )
                else:
                    raise RuntimeError("Remotion not available")
            except Exception as e:
                logger.warning(f"[Phase 4] Remotion failed ({e}), falling back to FFmpeg...")
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: _render_video_ffmpeg(
                        audio_path=mixed_audio_path,
                        output_path=video_path,
                        title=video_title,
                        duration=audio_duration,
                    ),
                )

            logger.info(f"[Phase 4] Video rendered: {video_path}")

            # ---- Phase 4.5: サムネイル生成 ----
            logger.info("[Phase 4.5] Generating thumbnail...")
            thumbnail_path = None
            try:
                from app.services.thumbnail_generator import ThumbnailGenerator

                thumb_gen = ThumbnailGenerator()
                thumb_output = str(VIDEO_OUTPUT_DIR / f"thumb_{job_id}.png")
                thumbnail_path = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: thumb_gen.generate(
                        title=video_title,
                        style="weekly_summary",
                        date_str=date_str,
                        output_path=thumb_output,
                    ),
                )
                logger.info(f"[Phase 4.5] Thumbnail generated: {thumbnail_path}")
            except Exception as e:
                logger.warning(f"[Phase 4.5] Thumbnail generation failed (non-fatal): {e}")

            # ---- Phase 5: YouTube アップロード ----
            logger.info("[Phase 5] Uploading to YouTube...")
            try:
                from app.services.youtube_uploader import YouTubeUploader

                uploader = YouTubeUploader()
                uploader.authenticate_with_tokens()

                # 動画説明文を構築
                company_names = ", ".join(
                    sorted(set(
                        a.get("company_name", "")
                        for a in analyses
                        if a.get("company_name")
                    ))
                )
                description = (
                    f"{date_str} 週間マーケットまとめ\n\n"
                    f"今週取り上げた企業: {company_names}\n\n"
                    f"AIアナリスト「イリス」による今週のIR分析まとめです。\n"
                    f"各企業の決算・開示情報をセクター別に解説します。\n\n"
                    f"※イリスの分析は参考情報です。投資判断はご自身の責任でお願いします。\n\n"
                    f"#IR分析 #週間まとめ #株式投資 #AIVTuber #イリス"
                )

                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: uploader.upload_video(
                        video_path=str(video_path),
                        title=video_title,
                        description=description,
                        tags=["IR分析", "週間まとめ", "株式投資", "マーケット", "イリス", "AIVTuber"],
                        category_id="22",
                        privacy_status="public",
                    ),
                )
                # サムネイル設定
                if thumbnail_path and result.get("video_id"):
                    try:
                        await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: uploader.set_thumbnail(
                                result["video_id"], thumbnail_path
                            ),
                        )
                        logger.info("[Phase 5] Thumbnail set on YouTube video")
                    except Exception as te:
                        logger.warning(f"[Phase 5] Thumbnail upload failed (non-fatal): {te}")

            except Exception as e:
                logger.error(f"[Phase 5] YouTube upload failed: {e}")
                raise

            logger.info(f"[Phase 5] Uploaded: {result.get('url', 'unknown')}")

            # ---- 完了 ----
            self.jobs["weekly_summary"]["last_run_status"] = "completed"
            self.jobs["weekly_summary"]["last_run_result"] = {
                "video_url": result.get("url"),
                "video_id": result.get("video_id"),
                "analyses_count": len(analyses),
                "audio_duration": audio_duration,
                "completed_at": datetime.now(JST).isoformat(),
            }
            logger.info(f"Weekly summary job completed: {result.get('url')}")

        except Exception as e:
            self.jobs["weekly_summary"]["last_run_status"] = "failed"
            self.jobs["weekly_summary"]["last_run_error"] = str(e)
            logger.error(f"Weekly summary job failed: {e}", exc_info=True)

    def cancel_job(self, job_id: str) -> bool:
        """
        ジョブをキャンセル

        Args:
            job_id: キャンセルするジョブのID

        Returns:
            bool: 成功したかどうか
        """
        try:
            self.scheduler.remove_job(job_id)
            if job_id in self.jobs:
                self.jobs[job_id]["status"] = "cancelled"
            logger.info(f"Job cancelled: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel job {job_id}: {str(e)}")
            return False

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        ジョブのステータスを取得

        Args:
            job_id: ジョブID

        Returns:
            Optional[Dict]: ジョブ情報
        """
        return self.jobs.get(job_id)

    def list_jobs(self) -> Dict[str, Dict[str, Any]]:
        """
        全ジョブの一覧を取得

        Returns:
            Dict: 全ジョブ情報
        """
        return self.jobs

    def reschedule_job(
        self,
        job_id: str,
        new_publish_time: datetime,
    ) -> Optional[Dict[str, Any]]:
        """
        ジョブを再スケジュール

        Args:
            job_id: ジョブID
            new_publish_time: 新しい公開時刻

        Returns:
            Optional[Dict]: 更新されたジョブ情報
        """
        if job_id not in self.jobs:
            return None

        try:
            self.scheduler.reschedule_job(
                job_id,
                trigger=DateTrigger(run_date=new_publish_time),
            )
            self.jobs[job_id]["publish_time"] = new_publish_time
            self.jobs[job_id]["updated_at"] = datetime.now()
            logger.info(f"Job rescheduled: {job_id} to {new_publish_time}")
            return self.jobs[job_id]
        except Exception as e:
            logger.error(f"Failed to reschedule job {job_id}: {str(e)}")
            return None


# グローバルスケジューラーインスタンス
scheduler = BroadcastScheduler()
