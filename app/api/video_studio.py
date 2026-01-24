"""
動画制作スタジオAPI

台本生成、音声生成、動画レンダリングなどのエンドポイントを提供
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum
import uuid
import os
import io
import wave
import struct
import logging
import httpx
import asyncio
import subprocess
import shutil
import shlex
from pathlib import Path

logger = logging.getLogger(__name__)

# 出力ディレクトリの作成
VIDEO_OUTPUT_DIR = Path(os.getenv("VIDEO_OUTPUT_DIR", "./static/videos"))
VIDEO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

AUDIO_OUTPUT_DIR = Path(os.getenv("AUDIO_OUTPUT_DIR", "./static/audio"))
AUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter(
    prefix="/studio",
    tags=["video-studio"],
    responses={404: {"description": "Not found"}},
)

# 設定
STATIC_AUDIO_DIR = os.getenv("STATIC_AUDIO_DIR", "/static/audio")
STATIC_VIDEO_DIR = os.getenv("STATIC_VIDEO_DIR", "/static/videos")
VOICEVOX_HOST = os.getenv("VOICEVOX_HOST", "http://localhost:50021")

# インメモリストレージ（本番環境ではRedisやDBを使用）
video_jobs: Dict[str, Dict[str, Any]] = {}
generated_videos: Dict[str, Dict[str, Any]] = {}


# ========== Enums ==========

class ScriptTheme(str, Enum):
    """台本のテーマ種別"""
    MARKET_COMMENT = "market_comment"
    IR_ANALYSIS = "ir_analysis"
    TERM_EXPLANATION = "term_explanation"


class VideoStatus(str, Enum):
    """動画レンダリングステータス"""
    QUEUED = "queued"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"


# ========== Request/Response Schemas ==========

# --- 台本生成 ---

class ScriptSegment(BaseModel):
    """台本のセグメント"""
    id: str = Field(..., description="セグメントID")
    type: str = Field(..., description="セグメントタイプ (intro/main/outro)")
    text: str = Field(..., description="セグメントのテキスト")
    speaker_id: int = Field(default=3, description="話者ID")
    notes: Optional[str] = Field(None, description="演出メモ")


class Script(BaseModel):
    """生成された台本"""
    title: str = Field(..., description="台本タイトル")
    theme: str = Field(..., description="テーマ")
    segments: List[ScriptSegment] = Field(..., description="台本セグメント")
    total_chars: int = Field(..., description="総文字数")
    estimated_duration: float = Field(..., description="推定再生時間（秒）")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ScriptGenerateRequest(BaseModel):
    """台本生成リクエスト"""
    theme: ScriptTheme = Field(..., description="台本テーマ")
    topic: Optional[str] = Field(None, description="トピック（オプション）")
    speaker_id: int = Field(default=3, description="デフォルト話者ID")

    class Config:
        json_schema_extra = {
            "example": {
                "theme": "market_comment",
                "topic": "今週の日経平均の動向",
                "speaker_id": 3
            }
        }


class ScriptGenerateResponse(BaseModel):
    """台本生成レスポンス"""
    script: Script


# --- 音声生成 ---

class AudioSegmentRequest(BaseModel):
    """音声生成用セグメント"""
    text: str = Field(..., description="読み上げテキスト")
    speaker_id: int = Field(default=3, description="話者ID")


class AudioGenerateRequest(BaseModel):
    """音声生成リクエスト"""
    segments: List[AudioSegmentRequest] = Field(..., description="セグメントリスト")
    output_filename: str = Field(..., description="出力ファイル名")

    class Config:
        json_schema_extra = {
            "example": {
                "segments": [
                    {"text": "皆さん、こんにちは！", "speaker_id": 3},
                    {"text": "今日は市場について解説します。", "speaker_id": 3}
                ],
                "output_filename": "market_comment_001.wav"
            }
        }


class AudioGenerateResponse(BaseModel):
    """音声生成レスポンス"""
    audio_url: str = Field(..., description="生成された音声ファイルのURL")
    duration: float = Field(..., description="再生時間（秒）")


# --- 動画レンダリング ---

class VideoSettings(BaseModel):
    """動画設定"""
    resolution: str = Field(default="1920x1080", description="解像度")
    fps: int = Field(default=30, description="フレームレート")
    background_color: str = Field(default="#1a1a2e", description="背景色")
    character_id: Optional[str] = Field(None, description="キャラクターID")


class VideoRenderRequest(BaseModel):
    """動画レンダリングリクエスト"""
    script: Script = Field(..., description="台本")
    audio_url: str = Field(..., description="音声ファイルURL")
    settings: Optional[VideoSettings] = Field(default_factory=VideoSettings)

    class Config:
        json_schema_extra = {
            "example": {
                "script": {
                    "title": "今週の市場コメント",
                    "theme": "market_comment",
                    "segments": [],
                    "total_chars": 500,
                    "estimated_duration": 60.0
                },
                "audio_url": "/static/audio/market_001.wav",
                "settings": {
                    "resolution": "1920x1080",
                    "fps": 30
                }
            }
        }


class VideoRenderResponse(BaseModel):
    """動画レンダリングレスポンス"""
    job_id: str = Field(..., description="ジョブID")
    status: VideoStatus = Field(..., description="ステータス")


class VideoStatusResponse(BaseModel):
    """動画ステータスレスポンス"""
    status: VideoStatus = Field(..., description="ステータス")
    progress: int = Field(default=0, description="進捗（0-100）")
    video_url: Optional[str] = Field(None, description="完成動画のURL")
    error: Optional[str] = Field(None, description="エラーメッセージ")


# --- 動画一覧 ---

class VideoInfo(BaseModel):
    """動画情報"""
    id: str = Field(..., description="動画ID")
    title: str = Field(..., description="タイトル")
    created_at: datetime = Field(..., description="作成日時")
    url: str = Field(..., description="動画URL")
    duration: Optional[float] = Field(None, description="再生時間（秒）")
    thumbnail_url: Optional[str] = Field(None, description="サムネイルURL")


class VideoListResponse(BaseModel):
    """動画一覧レスポンス"""
    videos: List[VideoInfo] = Field(..., description="動画リスト")
    total: int = Field(..., description="総数")


# ========== テンプレートベース台本生成 ==========

class ScriptTemplates:
    """台本テンプレート（後でLLM連携に置き換え可能）"""

    @staticmethod
    def market_comment(topic: Optional[str] = None) -> Dict[str, Any]:
        """市場コメント用テンプレート"""
        topic_text = topic or "今日の市場動向"
        return {
            "title": f"【市場解説】{topic_text}",
            "segments": [
                {
                    "id": "intro",
                    "type": "intro",
                    "text": f"皆さん、こんにちは！本日は「{topic_text}」についてお話しします。",
                    "notes": "明るいトーンで"
                },
                {
                    "id": "main_1",
                    "type": "main",
                    "text": "まず、本日の市場の動きを振り返ってみましょう。日経平均株価は堅調に推移し、投資家心理も改善傾向にあります。",
                    "notes": "落ち着いたトーンで解説"
                },
                {
                    "id": "main_2",
                    "type": "main",
                    "text": "特に注目すべきは、海外市場の影響です。米国市場の動向が日本市場にも波及していますね。",
                    "notes": "解説調"
                },
                {
                    "id": "outro",
                    "type": "outro",
                    "text": "以上、本日の市場解説でした。次回の配信もお楽しみに！",
                    "notes": "締めくくり"
                }
            ]
        }

    @staticmethod
    def ir_analysis(topic: Optional[str] = None) -> Dict[str, Any]:
        """IR分析用テンプレート"""
        company = topic or "注目企業"
        return {
            "title": f"【IR分析】{company}の決算を読み解く",
            "segments": [
                {
                    "id": "intro",
                    "type": "intro",
                    "text": f"皆さん、こんにちは！今回は{company}のIR情報について詳しく分析していきます。",
                    "notes": "専門的だが親しみやすく"
                },
                {
                    "id": "main_1",
                    "type": "main",
                    "text": "まず、直近の決算内容を確認してみましょう。売上高と営業利益の推移に注目です。",
                    "notes": "数字を丁寧に説明"
                },
                {
                    "id": "main_2",
                    "type": "main",
                    "text": "次に、今後の成長戦略についてです。中期経営計画で示された目標と施策を見ていきましょう。",
                    "notes": "将来展望"
                },
                {
                    "id": "main_3",
                    "type": "main",
                    "text": "投資判断のポイントをまとめると、収益性の改善と成長投資のバランスがカギとなります。",
                    "notes": "まとめ"
                },
                {
                    "id": "outro",
                    "type": "outro",
                    "text": "以上、IR分析でした。投資判断は自己責任でお願いいたします。ご視聴ありがとうございました！",
                    "notes": "免責事項を含む"
                }
            ]
        }

    @staticmethod
    def term_explanation(topic: Optional[str] = None) -> Dict[str, Any]:
        """用語解説用テンプレート"""
        term = topic or "PER（株価収益率）"
        return {
            "title": f"【用語解説】{term}とは？",
            "segments": [
                {
                    "id": "intro",
                    "type": "intro",
                    "text": f"皆さん、こんにちは！今回は投資用語「{term}」について分かりやすく解説します。",
                    "notes": "教育的なトーン"
                },
                {
                    "id": "main_1",
                    "type": "main",
                    "text": "まず、基本的な定義から説明しますね。この指標は投資判断において非常に重要な役割を果たします。",
                    "notes": "基礎から説明"
                },
                {
                    "id": "main_2",
                    "type": "main",
                    "text": "具体的な計算方法と、実際の投資でどう活用するかを見ていきましょう。",
                    "notes": "実践的な説明"
                },
                {
                    "id": "main_3",
                    "type": "main",
                    "text": "注意点として、この指標だけで判断せず、他の指標と組み合わせることが大切です。",
                    "notes": "注意喚起"
                },
                {
                    "id": "outro",
                    "type": "outro",
                    "text": "以上、用語解説でした。他にも知りたい用語があればコメントで教えてくださいね！",
                    "notes": "視聴者エンゲージメント"
                }
            ]
        }


# ========== ヘルパー関数 ==========

def generate_script_from_template(theme: ScriptTheme, topic: Optional[str], speaker_id: int) -> Script:
    """テンプレートから台本を生成"""
    template_map = {
        ScriptTheme.MARKET_COMMENT: ScriptTemplates.market_comment,
        ScriptTheme.IR_ANALYSIS: ScriptTemplates.ir_analysis,
        ScriptTheme.TERM_EXPLANATION: ScriptTemplates.term_explanation,
    }

    template_func = template_map.get(theme)
    if not template_func:
        raise ValueError(f"Unknown theme: {theme}")

    template = template_func(topic)

    segments = []
    total_chars = 0
    for seg in template["segments"]:
        segment = ScriptSegment(
            id=seg["id"],
            type=seg["type"],
            text=seg["text"],
            speaker_id=speaker_id,
            notes=seg.get("notes")
        )
        segments.append(segment)
        total_chars += len(seg["text"])

    # 1秒あたり約5文字として推定
    estimated_duration = total_chars / 5.0

    return Script(
        title=template["title"],
        theme=theme.value,
        segments=segments,
        total_chars=total_chars,
        estimated_duration=estimated_duration
    )


def concatenate_wav_files(wav_data_list: List[bytes], silence_duration: float = 0.3) -> bytes:
    """
    複数のWAVファイルを結合する

    Args:
        wav_data_list: WAVファイルのバイトデータのリスト
        silence_duration: セグメント間の無音時間（秒）

    Returns:
        結合されたWAVファイルのバイトデータ
    """
    if not wav_data_list:
        raise ValueError("No WAV data to concatenate")

    # 最初のWAVファイルからパラメータを取得
    first_wav = io.BytesIO(wav_data_list[0])
    with wave.open(first_wav, 'rb') as wav_file:
        n_channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        frame_rate = wav_file.getframerate()

    # 無音フレームを生成
    silence_frames = int(frame_rate * silence_duration)
    silence_data = b'\x00' * (silence_frames * n_channels * sample_width)

    # 出力バッファ
    output = io.BytesIO()

    with wave.open(output, 'wb') as output_wav:
        output_wav.setnchannels(n_channels)
        output_wav.setsampwidth(sample_width)
        output_wav.setframerate(frame_rate)

        for i, wav_data in enumerate(wav_data_list):
            wav_buffer = io.BytesIO(wav_data)
            try:
                with wave.open(wav_buffer, 'rb') as wav_file:
                    # フレームレートが一致するか確認
                    if wav_file.getframerate() != frame_rate:
                        logger.warning(f"Frame rate mismatch: expected {frame_rate}, got {wav_file.getframerate()}")
                        continue

                    frames = wav_file.readframes(wav_file.getnframes())
                    output_wav.writeframes(frames)

                    # 最後のセグメント以外は無音を追加
                    if i < len(wav_data_list) - 1:
                        output_wav.writeframes(silence_data)

            except wave.Error as e:
                logger.error(f"Error reading WAV segment {i}: {e}")
                continue

    return output.getvalue()


def calculate_wav_duration(wav_data: bytes) -> float:
    """WAVファイルの再生時間を計算"""
    try:
        wav_buffer = io.BytesIO(wav_data)
        with wave.open(wav_buffer, 'rb') as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            return frames / float(rate)
    except Exception as e:
        logger.error(f"Error calculating WAV duration: {e}")
        return 0.0


# セキュリティ: 許可された解像度のホワイトリスト
ALLOWED_RESOLUTIONS = {
    "1920x1080", "1280x720", "854x480", "640x360",
    "1080x1920", "720x1280"  # 縦動画用
}

# セキュリティ: FPS制限
MIN_FPS = 24
MAX_FPS = 60


def validate_video_settings(settings: "VideoSettings") -> None:
    """動画設定のバリデーション"""
    if settings.resolution not in ALLOWED_RESOLUTIONS:
        raise ValueError(f"Invalid resolution: {settings.resolution}. Allowed: {ALLOWED_RESOLUTIONS}")

    if not (MIN_FPS <= settings.fps <= MAX_FPS):
        raise ValueError(f"Invalid FPS: {settings.fps}. Must be between {MIN_FPS} and {MAX_FPS}")

    # 背景色の検証（#RRGGBB形式）
    bg_color = settings.background_color
    if not (bg_color.startswith("#") and len(bg_color) == 7):
        raise ValueError(f"Invalid background color format: {bg_color}")
    try:
        int(bg_color[1:], 16)
    except ValueError:
        raise ValueError(f"Invalid background color: {bg_color}")


def escape_ffmpeg_text(text: str) -> str:
    """FFmpegのdrawtextフィルター用にテキストをエスケープ"""
    # FFmpegのdrawtextで使用する特殊文字をエスケープ
    escape_chars = [
        ("\\", "\\\\\\\\"),  # バックスラッシュは最初に
        ("'", "\\\\'"),
        (":", "\\\\:"),
        ("[", "\\\\["),
        ("]", "\\\\]"),
        ("{", "\\\\{"),
        ("}", "\\\\}"),
        (",", "\\\\,"),
        (";", "\\\\;"),
    ]
    result = text
    for char, escaped in escape_chars:
        result = result.replace(char, escaped)
    return result


def generate_video_with_ffmpeg(
    job_id: str,
    script: Script,
    settings: VideoSettings,
    audio_path: Optional[str] = None,
    character_image_path: Optional[str] = None
) -> str:
    """FFmpegを使用して動画を生成する"""

    # セキュリティ: 設定をバリデーション
    validate_video_settings(settings)

    output_path = VIDEO_OUTPUT_DIR / f"{job_id}.mp4"

    # 解像度をパース（バリデーション済み）
    width, height = settings.resolution.split("x")
    width, height = int(width), int(height)

    # 背景色を#ffffffからffffffへ変換（バリデーション済み）
    bg_color = settings.background_color.lstrip("#")

    # 動画の長さを計算（秒）- 上限を設定
    duration = min(max(script.estimated_duration, 10), 600)  # 最低10秒、最大10分

    # タイトルテキストを安全にエスケープ
    title_text = escape_ffmpeg_text(script.title[:100])  # 100文字に制限

    # 字幕用のセグメントテキストを結合（最初のセグメントのみ表示）
    subtitle_text = ""
    if script.segments:
        subtitle_text = escape_ffmpeg_text(script.segments[0].text[:150])

    # キャラクター画像のパス（デフォルト）
    if character_image_path is None:
        # プロジェクトルートからの相対パス
        default_character = Path(__file__).parent.parent.parent / "frontend" / "public" / "images" / "iris" / "iris-normal.png"
        if default_character.exists():
            character_image_path = str(default_character)

    # フィルターチェーンを構築
    filters = []

    # 背景色
    input_source = f"color=c={bg_color}:s={width}x{height}:d={duration}:r={settings.fps}"

    # タイトルテキスト（上部）
    filters.append(
        f"drawtext=text='{title_text}'"
        f":fontcolor=white:fontsize=42:x=(w-text_w)/2:y=60"
        f":shadowcolor=black:shadowx=2:shadowy=2"
    )

    # 字幕テキスト（下部）
    if subtitle_text:
        filters.append(
            f"drawtext=text='{subtitle_text}'"
            f":fontcolor=white:fontsize=32:x=(w-text_w)/2:y=h-120"
            f":shadowcolor=black:shadowx=2:shadowy=2"
            f":box=1:boxcolor=black@0.6:boxborderw=10"
        )

    # FFmpegコマンドを構築
    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", input_source,
    ]

    # キャラクター画像がある場合は重ねる
    if character_image_path and Path(character_image_path).exists():
        ffmpeg_cmd.extend(["-i", character_image_path])
        # キャラクターを右下に配置
        overlay_filter = (
            f"[0:v][1:v]overlay=W-w-50:H-h-20:format=auto"
        )
        filter_complex = f"{overlay_filter},{','.join(filters)}" if filters else overlay_filter
        ffmpeg_cmd.extend(["-filter_complex", filter_complex])
    else:
        # キャラクターなしの場合
        if filters:
            ffmpeg_cmd.extend(["-vf", ",".join(filters)])

    # 音声がある場合は追加
    if audio_path and Path(audio_path).exists():
        ffmpeg_cmd.extend([
            "-i", audio_path,
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest"  # 音声と動画の短い方に合わせる
        ])

    ffmpeg_cmd.extend([
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path)
    ])

    logger.info(f"Running FFmpeg with {len(ffmpeg_cmd)} arguments")
    logger.debug(f"FFmpeg command: {' '.join(ffmpeg_cmd)}")

    try:
        result = subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            text=True,
            timeout=300,
            shell=False  # セキュリティ: シェル経由で実行しない
        )

        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr}")
            raise Exception(f"FFmpeg failed: {result.stderr[:500]}")

        logger.info(f"Video generated: {output_path}")
        return str(output_path)

    except subprocess.TimeoutExpired:
        raise Exception("FFmpeg rendering timed out (max 5 minutes)")
    except FileNotFoundError:
        raise Exception("FFmpeg not found. Please install FFmpeg.")


def resolve_audio_path(audio_url: str) -> Optional[str]:
    """音声URLから実際のファイルパスを解決"""
    if not audio_url:
        return None

    # /static/audio/ で始まる場合
    if audio_url.startswith("/static/audio/"):
        filename = audio_url.replace("/static/audio/", "")
        audio_path = AUDIO_OUTPUT_DIR / filename
        if audio_path.exists():
            return str(audio_path)

    # 絶対パスの場合
    if Path(audio_url).exists():
        return audio_url

    return None


async def render_video_task(job_id: str, script: Script, audio_url: str, settings: VideoSettings):
    """動画レンダリングのバックグラウンドタスク"""
    try:
        video_jobs[job_id]["status"] = VideoStatus.RENDERING
        video_jobs[job_id]["progress"] = 10

        logger.info(f"Starting video rendering for job: {job_id}")

        # FFmpegが利用可能かチェック
        ffmpeg_available = shutil.which("ffmpeg") is not None

        if ffmpeg_available:
            video_jobs[job_id]["progress"] = 20

            # 音声ファイルパスを解決
            audio_path = resolve_audio_path(audio_url)
            if audio_path:
                logger.info(f"Using audio file: {audio_path}")
            else:
                logger.warning(f"Audio file not found: {audio_url}")

            video_jobs[job_id]["progress"] = 30

            # ブロッキング処理をスレッドプールで実行
            loop = asyncio.get_event_loop()

            # functools.partialを使って引数を渡す
            from functools import partial
            render_func = partial(
                generate_video_with_ffmpeg,
                job_id=job_id,
                script=script,
                settings=settings,
                audio_path=audio_path,
                character_image_path=None  # デフォルトのキャラクター画像を使用
            )

            output_path = await loop.run_in_executor(None, render_func)

            video_jobs[job_id]["progress"] = 90

            # 動画URLを設定
            video_url = f"/api/studio/video/download/{job_id}"

        else:
            # FFmpegがない場合はモックモード
            logger.warning("FFmpeg not available, using mock mode")
            for progress in [20, 40, 60, 80]:
                await asyncio.sleep(0.5)
                video_jobs[job_id]["progress"] = progress

            video_url = f"/api/studio/video/download/{job_id}"

        video_jobs[job_id]["progress"] = 100
        video_jobs[job_id]["status"] = VideoStatus.COMPLETED
        video_jobs[job_id]["video_url"] = video_url
        video_jobs[job_id]["completed_at"] = datetime.utcnow()

        # 動画情報を保存
        generated_videos[job_id] = {
            "id": job_id,
            "title": script.title,
            "created_at": datetime.utcnow(),
            "url": video_url,
            "duration": script.estimated_duration,
            "thumbnail_url": None
        }

        logger.info(f"Video rendering completed: {job_id}")

    except Exception as e:
        logger.error(f"Video rendering failed: {job_id}, error: {str(e)}")
        video_jobs[job_id]["status"] = VideoStatus.FAILED
        video_jobs[job_id]["error"] = str(e)


# ========== API Endpoints ==========

# --- 台本生成 ---

@router.post("/script/generate", response_model=ScriptGenerateResponse)
async def generate_script(request: ScriptGenerateRequest):
    """
    台本を生成する

    テーマに基づいてテンプレートから台本を生成します。
    将来的にはLLMを使用した高度な台本生成に拡張可能です。

    - theme: market_comment（市場コメント）、ir_analysis（IR分析）、term_explanation（用語解説）
    - topic: オプションのトピック指定
    - speaker_id: VOICEVOXの話者ID
    """
    try:
        script = generate_script_from_template(
            theme=request.theme,
            topic=request.topic,
            speaker_id=request.speaker_id
        )

        logger.info(f"Script generated: {script.title}")

        return ScriptGenerateResponse(script=script)

    except Exception as e:
        logger.error(f"Script generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Script generation failed: {str(e)}")


# --- 音声生成 ---

@router.post("/audio/generate", response_model=AudioGenerateResponse)
async def generate_audio(request: AudioGenerateRequest):
    """
    台本セグメントから音声を生成する

    VOICEVOXを使用してテキストを音声に変換し、WAVファイルとして保存します。

    - segments: 読み上げるテキストと話者IDのリスト
    - output_filename: 出力ファイル名（.wav拡張子）
    """
    if not request.segments:
        raise HTTPException(status_code=400, detail="Segments cannot be empty")

    # ファイル名のバリデーション
    if not request.output_filename.endswith(".wav"):
        raise HTTPException(status_code=400, detail="Output filename must end with .wav")

    # パストラバーサル対策
    safe_filename = os.path.basename(request.output_filename)
    if safe_filename != request.output_filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    try:
        audio_chunks: List[bytes] = []
        retry_count = 3

        async with httpx.AsyncClient(timeout=120.0) as client:
            for segment in request.segments:
                if not segment.text.strip():
                    continue

                # テキスト長制限（セキュリティ）
                if len(segment.text) > 1000:
                    logger.warning(f"Text too long, truncating: {len(segment.text)} chars")
                    text = segment.text[:1000]
                else:
                    text = segment.text

                # リトライロジック付きでVOICEVOX API呼び出し
                wav_data = None
                last_error = None

                for attempt in range(retry_count):
                    try:
                        # VOICEVOX audio_query
                        query_response = await client.post(
                            f"{VOICEVOX_HOST}/audio_query",
                            params={
                                "text": text,
                                "speaker": segment.speaker_id,
                            },
                        )

                        if query_response.status_code != 200:
                            last_error = f"audio_query failed: {query_response.text}"
                            continue

                        audio_query = query_response.json()

                        # VOICEVOX synthesis
                        synthesis_response = await client.post(
                            f"{VOICEVOX_HOST}/synthesis",
                            params={"speaker": segment.speaker_id},
                            json=audio_query,
                        )

                        if synthesis_response.status_code != 200:
                            last_error = f"synthesis failed: {synthesis_response.text}"
                            continue

                        wav_data = synthesis_response.content
                        break

                    except httpx.TimeoutException:
                        last_error = "Request timed out"
                        await asyncio.sleep(1 * (attempt + 1))  # exponential backoff
                        continue

                if wav_data is None:
                    logger.error(f"Failed to generate audio after {retry_count} attempts: {last_error}")
                    raise HTTPException(
                        status_code=502,
                        detail=f"VOICEVOX failed after {retry_count} attempts: {last_error}"
                    )

                audio_chunks.append(wav_data)

        if not audio_chunks:
            raise HTTPException(status_code=400, detail="No audio generated (all segments were empty)")

        # 音声ファイルを結合
        combined_wav = concatenate_wav_files(audio_chunks, silence_duration=0.3)

        # 再生時間を計算
        total_duration = calculate_wav_duration(combined_wav)

        # ファイルに保存
        output_path = AUDIO_OUTPUT_DIR / safe_filename
        with open(output_path, 'wb') as f:
            f.write(combined_wav)

        # 公開URLを生成
        audio_url = f"/static/audio/{safe_filename}"

        logger.info(f"Audio generated and saved: {output_path}, duration: {total_duration}s")

        return AudioGenerateResponse(
            audio_url=audio_url,
            duration=round(total_duration, 2)
        )

    except httpx.ConnectError:
        logger.error(f"Cannot connect to VOICEVOX at {VOICEVOX_HOST}")
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to VOICEVOX. Please ensure VOICEVOX is running at {VOICEVOX_HOST}"
        )
    except httpx.TimeoutException:
        logger.error("VOICEVOX request timed out")
        raise HTTPException(
            status_code=504,
            detail="VOICEVOX request timed out"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Audio generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Audio generation failed: {str(e)}")


# --- 動画レンダリング ---

@router.post("/video/render", response_model=VideoRenderResponse)
async def render_video(
    request: VideoRenderRequest,
    background_tasks: BackgroundTasks
):
    """
    動画をレンダリングする（非同期）

    台本と音声から動画を生成します。処理はバックグラウンドで実行され、
    ジョブIDを使用してステータスを確認できます。

    - script: 台本データ
    - audio_url: 音声ファイルのURL
    - settings: 動画設定（解像度、FPSなど）
    """
    job_id = str(uuid.uuid4())

    # ジョブを初期化
    video_jobs[job_id] = {
        "status": VideoStatus.QUEUED,
        "progress": 0,
        "video_url": None,
        "error": None,
        "created_at": datetime.utcnow(),
        "script_title": request.script.title,
    }

    # バックグラウンドでレンダリング開始
    settings = request.settings or VideoSettings()
    background_tasks.add_task(
        render_video_task,
        job_id,
        request.script,
        request.audio_url,
        settings
    )

    logger.info(f"Video rendering job queued: {job_id}")

    return VideoRenderResponse(
        job_id=job_id,
        status=VideoStatus.QUEUED
    )


@router.get("/video/status/{job_id}", response_model=VideoStatusResponse)
async def get_video_status(job_id: str):
    """
    動画レンダリングのステータスを取得する

    - job_id: レンダリングジョブのID
    """
    if job_id not in video_jobs:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    job = video_jobs[job_id]

    return VideoStatusResponse(
        status=job["status"],
        progress=job["progress"],
        video_url=job.get("video_url"),
        error=job.get("error")
    )


# --- 動画一覧 ---

@router.get("/videos", response_model=VideoListResponse)
async def list_videos():
    """
    生成済み動画の一覧を取得する
    """
    videos = [
        VideoInfo(
            id=video["id"],
            title=video["title"],
            created_at=video["created_at"],
            url=video["url"],
            duration=video.get("duration"),
            thumbnail_url=video.get("thumbnail_url")
        )
        for video in generated_videos.values()
    ]

    # 作成日時の降順でソート
    videos.sort(key=lambda v: v.created_at, reverse=True)

    return VideoListResponse(
        videos=videos,
        total=len(videos)
    )


# --- ヘルスチェック ---

@router.get("/health")
async def studio_health_check():
    """
    Video Studio APIのヘルスチェック
    """
    voicevox_status = "unknown"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{VOICEVOX_HOST}/version")
            if response.status_code == 200:
                voicevox_status = "healthy"
            else:
                voicevox_status = "unhealthy"
    except Exception:
        voicevox_status = "unavailable"

    return {
        "status": "healthy",
        "voicevox_status": voicevox_status,
        "voicevox_host": VOICEVOX_HOST,
        "pending_jobs": len([j for j in video_jobs.values() if j["status"] in [VideoStatus.QUEUED, VideoStatus.RENDERING]]),
        "completed_videos": len(generated_videos),
    }


# --- 動画ダウンロード ---

@router.get("/video/download/{job_id}")
async def download_video(job_id: str):
    """
    生成された動画をダウンロードする

    - job_id: レンダリングジョブのID
    """
    from fastapi.responses import FileResponse

    # ジョブの存在確認
    if job_id not in video_jobs:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    job = video_jobs[job_id]

    # レンダリング完了確認
    if job["status"] != VideoStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Video is not ready. Current status: {job['status']}"
        )

    # ファイルパスを構築
    video_path = VIDEO_OUTPUT_DIR / f"{job_id}.mp4"

    # ファイル存在確認
    if not video_path.exists():
        # ファイルがない場合は、ダミー動画を生成
        logger.warning(f"Video file not found: {video_path}, generating placeholder")

        # ダミー動画を生成（FFmpegがあれば）
        if shutil.which("ffmpeg"):
            try:
                script_title = job.get("script_title", "SmartIR Video")
                subprocess.run([
                    "ffmpeg", "-y",
                    "-f", "lavfi",
                    "-i", "color=c=1e1b4b:s=1920x1080:d=5:r=30",
                    "-vf", f"drawtext=text='{script_title}':fontcolor=white:fontsize=48:x=(w-text_w)/2:y=h/2-24",
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-pix_fmt", "yuv420p",
                    str(video_path)
                ], capture_output=True, timeout=60)
            except Exception as e:
                logger.error(f"Failed to generate placeholder video: {e}")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to generate video file"
                )
        else:
            raise HTTPException(
                status_code=500,
                detail="Video file not found and FFmpeg is not available"
            )

    # 動画情報を取得（タイトル用）
    video_info = generated_videos.get(job_id, {})
    title = video_info.get("title", "smartir-video")
    # ファイル名に使えない文字を除去
    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
    safe_title = safe_title.replace(' ', '_') or "video"

    logger.info(f"Serving video file: {video_path}")

    return FileResponse(
        path=str(video_path),
        media_type="video/mp4",
        filename=f"{safe_title}_{job_id[:8]}.mp4",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_title}_{job_id[:8]}.mp4"'
        }
    )


# --- 最新動画ダウンロード（事前生成済み動画） ---

@router.get("/video/latest")
async def download_latest_video():
    """
    事前生成済みの最新動画をダウンロードする

    frontend/out/video.mp4 に存在する動画ファイルを返します。
    これはRemotionで事前にレンダリングされた動画です。
    """
    # frontend/out/video.mp4 のパスを構築
    video_path = Path(__file__).parent.parent.parent / "frontend" / "out" / "video.mp4"

    logger.info(f"Looking for video at: {video_path}")

    if not video_path.exists():
        logger.error(f"Video file not found: {video_path}")
        raise HTTPException(
            status_code=404,
            detail="No pre-rendered video found. Please render a video first using Remotion."
        )

    logger.info(f"Serving latest video: {video_path}")

    return FileResponse(
        path=str(video_path),
        media_type="video/mp4",
        filename="iris-video.mp4",
        headers={
            "Content-Disposition": 'attachment; filename="iris-video.mp4"'
        }
    )


# ========== ワンクリック動画生成 ==========

class FullVideoGenerateRequest(BaseModel):
    """一気通貫動画生成リクエスト"""
    theme: ScriptTheme = Field(..., description="台本テーマ")
    topic: Optional[str] = Field(None, description="トピック（オプション）")
    speaker_id: int = Field(default=3, description="話者ID")
    settings: Optional[VideoSettings] = Field(default_factory=VideoSettings)
    enable_lipsync: bool = Field(default=False, description="SadTalkerリップシンクを有効化")
    character_image_url: Optional[str] = Field(None, description="リップシンク用キャラクター画像URL")

    class Config:
        json_schema_extra = {
            "example": {
                "theme": "market_comment",
                "topic": "今日の日経平均",
                "speaker_id": 3,
                "settings": {
                    "resolution": "1920x1080",
                    "fps": 30
                },
                "enable_lipsync": False
            }
        }


class FullVideoGenerateResponse(BaseModel):
    """一気通貫動画生成レスポンス"""
    job_id: str
    status: VideoStatus
    script_title: str
    message: str


async def full_video_generation_task(
    job_id: str,
    theme: ScriptTheme,
    topic: Optional[str],
    speaker_id: int,
    settings: VideoSettings,
    enable_lipsync: bool = False,
    character_image_url: Optional[str] = None
):
    """一気通貫の動画生成バックグラウンドタスク"""
    try:
        video_jobs[job_id]["status"] = VideoStatus.RENDERING
        video_jobs[job_id]["progress"] = 5
        video_jobs[job_id]["stage"] = "script_generation"

        logger.info(f"Starting full video generation: {job_id}, lipsync={enable_lipsync}")

        # Step 1: 台本生成
        script = generate_script_from_template(
            theme=theme,
            topic=topic,
            speaker_id=speaker_id
        )
        video_jobs[job_id]["progress"] = 15
        video_jobs[job_id]["script_title"] = script.title
        logger.info(f"Script generated: {script.title}")

        # Step 2: 音声生成
        video_jobs[job_id]["stage"] = "audio_generation"
        video_jobs[job_id]["progress"] = 20

        audio_chunks: List[bytes] = []
        voicevox_available = True

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                # VOICEVOX接続確認
                try:
                    await client.get(f"{VOICEVOX_HOST}/version")
                except Exception:
                    voicevox_available = False
                    logger.warning("VOICEVOX not available, skipping audio generation")

                if voicevox_available:
                    total_segments = len(script.segments)
                    for i, segment in enumerate(script.segments):
                        if not segment.text.strip():
                            continue

                        # audio_query
                        query_response = await client.post(
                            f"{VOICEVOX_HOST}/audio_query",
                            params={"text": segment.text[:1000], "speaker": segment.speaker_id},
                        )

                        if query_response.status_code != 200:
                            logger.warning(f"audio_query failed for segment {i}")
                            continue

                        audio_query = query_response.json()

                        # synthesis
                        synthesis_response = await client.post(
                            f"{VOICEVOX_HOST}/synthesis",
                            params={"speaker": segment.speaker_id},
                            json=audio_query,
                        )

                        if synthesis_response.status_code == 200:
                            audio_chunks.append(synthesis_response.content)

                        # 進捗更新
                        progress = 20 + int(40 * (i + 1) / total_segments)
                        video_jobs[job_id]["progress"] = progress

        except Exception as e:
            logger.warning(f"Audio generation error: {e}")

        # 音声ファイルを保存
        audio_path = None
        if audio_chunks:
            try:
                combined_wav = concatenate_wav_files(audio_chunks)
                audio_filename = f"{job_id}_audio.wav"
                audio_file_path = AUDIO_OUTPUT_DIR / audio_filename
                with open(audio_file_path, 'wb') as f:
                    f.write(combined_wav)
                audio_path = str(audio_file_path)
                logger.info(f"Audio saved: {audio_path}")
            except Exception as e:
                logger.warning(f"Failed to save audio: {e}")

        video_jobs[job_id]["progress"] = 60

        # Step 3: 動画レンダリング
        video_jobs[job_id]["stage"] = "video_rendering"

        ffmpeg_available = shutil.which("ffmpeg") is not None

        if ffmpeg_available:
            video_jobs[job_id]["progress"] = 70

            loop = asyncio.get_event_loop()
            from functools import partial

            render_func = partial(
                generate_video_with_ffmpeg,
                job_id=job_id,
                script=script,
                settings=settings,
                audio_path=audio_path,
                character_image_path=None
            )

            await loop.run_in_executor(None, render_func)

            video_jobs[job_id]["progress"] = 85
        else:
            # モックモード
            for progress in [70, 80]:
                await asyncio.sleep(0.3)
                video_jobs[job_id]["progress"] = progress

        # Step 4: リップシンク（オプション）
        lipsync_video_url = None
        if enable_lipsync and audio_path:
            video_jobs[job_id]["stage"] = "lipsync_generation"
            video_jobs[job_id]["progress"] = 88

            try:
                from app.services.sadtalker import sadtalker_service

                # キャラクター画像を解決
                char_image_path = None
                if character_image_url:
                    # URLからパスを解決
                    if character_image_url.startswith("/"):
                        potential_path = Path(__file__).parent.parent.parent / "frontend" / "public" / character_image_url.lstrip("/")
                        if potential_path.exists():
                            char_image_path = str(potential_path)

                if not char_image_path:
                    # デフォルトのキャラクター画像
                    default_char = Path(__file__).parent.parent.parent / "frontend" / "public" / "images" / "iris" / "iris-normal.png"
                    if default_char.exists():
                        char_image_path = str(default_char)

                if char_image_path and sadtalker_service.check_models_installed():
                    logger.info(f"Starting SadTalker lipsync: image={char_image_path}, audio={audio_path}")

                    # SadTalkerジョブ作成
                    lipsync_job = sadtalker_service.create_job()

                    # リップシンク動画生成
                    lipsync_result = await sadtalker_service.generate_video(
                        job_id=lipsync_job.job_id,
                        image_path=char_image_path,
                        audio_path=audio_path,
                        enhancer="gfpgan",
                        still_mode=False,
                        size=256
                    )

                    if lipsync_result:
                        lipsync_video_url = f"/api/sadtalker/download/{lipsync_job.job_id}"
                        video_jobs[job_id]["lipsync_video_url"] = lipsync_video_url
                        logger.info(f"Lipsync video generated: {lipsync_video_url}")
                    else:
                        logger.warning("Lipsync generation failed, continuing without lipsync")
                else:
                    logger.warning("SadTalker not available or character image not found")

            except Exception as e:
                logger.warning(f"Lipsync generation error: {e}, continuing without lipsync")

            video_jobs[job_id]["progress"] = 95

        # 完了
        video_jobs[job_id]["progress"] = 100
        video_jobs[job_id]["status"] = VideoStatus.COMPLETED
        video_jobs[job_id]["video_url"] = f"/api/studio/video/download/{job_id}"
        video_jobs[job_id]["completed_at"] = datetime.utcnow()
        video_jobs[job_id]["stage"] = "completed"

        if lipsync_video_url:
            video_jobs[job_id]["lipsync_video_url"] = lipsync_video_url

        # 動画情報を保存
        generated_videos[job_id] = {
            "id": job_id,
            "title": script.title,
            "created_at": datetime.utcnow(),
            "url": f"/api/studio/video/download/{job_id}",
            "duration": script.estimated_duration,
            "thumbnail_url": None
        }

        logger.info(f"Full video generation completed: {job_id}")

    except Exception as e:
        logger.error(f"Full video generation failed: {job_id}, error: {str(e)}")
        video_jobs[job_id]["status"] = VideoStatus.FAILED
        video_jobs[job_id]["error"] = str(e)


@router.post("/video/generate-full", response_model=FullVideoGenerateResponse)
async def generate_full_video(
    request: FullVideoGenerateRequest,
    background_tasks: BackgroundTasks
):
    """
    ワンクリックで動画を生成する（台本→音声→動画）

    テーマを指定するだけで、台本生成から動画レンダリングまでを一気通貫で実行します。

    - theme: market_comment（市場コメント）、ir_analysis（IR分析）、term_explanation（用語解説）
    - topic: オプションのトピック指定
    - speaker_id: VOICEVOXの話者ID
    - settings: 動画設定（解像度、FPSなど）
    """
    job_id = str(uuid.uuid4())

    # バリデーション
    settings = request.settings or VideoSettings()
    try:
        validate_video_settings(settings)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # ジョブを初期化
    video_jobs[job_id] = {
        "status": VideoStatus.QUEUED,
        "progress": 0,
        "video_url": None,
        "error": None,
        "created_at": datetime.utcnow(),
        "script_title": f"{request.theme.value} - {request.topic or ''}",
        "stage": "queued"
    }

    # バックグラウンドで実行
    background_tasks.add_task(
        full_video_generation_task,
        job_id,
        request.theme,
        request.topic,
        request.speaker_id,
        settings,
        request.enable_lipsync,
        request.character_image_url
    )

    logger.info(f"Full video generation job queued: {job_id}")

    return FullVideoGenerateResponse(
        job_id=job_id,
        status=VideoStatus.QUEUED,
        script_title=video_jobs[job_id]["script_title"],
        message="動画生成を開始しました。/api/studio/video/status/{job_id} で進捗を確認できます。"
    )
