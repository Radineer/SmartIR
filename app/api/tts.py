from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx
import base64
import os
import logging
import struct

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/tts",
    tags=["tts"],
    responses={404: {"description": "Not found"}},
)

# VOICEVOX設定
VOICEVOX_HOST = os.getenv("VOICEVOX_HOST", "http://localhost:50021")


class TTSRequest(BaseModel):
    text: str
    speaker_id: int = 3  # VOICEVOX話者ID（デフォルト: ずんだもん）


class TTSResponse(BaseModel):
    audio_base64: str
    duration_seconds: float


def calculate_wav_duration(wav_data: bytes) -> float:
    """WAVファイルのバイナリデータから再生時間を計算"""
    try:
        # WAVヘッダーを解析
        # サンプルレート: byte 24-27
        # バイトレート: byte 28-31
        if len(wav_data) < 44:
            return 0.0

        # RIFFヘッダー確認
        if wav_data[:4] != b'RIFF' or wav_data[8:12] != b'WAVE':
            return 0.0

        # サンプルレートとチャンネル数、ビット深度から計算
        channels = struct.unpack('<H', wav_data[22:24])[0]
        sample_rate = struct.unpack('<I', wav_data[24:28])[0]
        bits_per_sample = struct.unpack('<H', wav_data[34:36])[0]

        # データサイズを取得（dataチャンクを探す）
        data_size = 0
        pos = 12
        while pos < len(wav_data) - 8:
            chunk_id = wav_data[pos:pos+4]
            chunk_size = struct.unpack('<I', wav_data[pos+4:pos+8])[0]
            if chunk_id == b'data':
                data_size = chunk_size
                break
            pos += 8 + chunk_size

        if data_size == 0 or sample_rate == 0:
            return 0.0

        # 再生時間 = データサイズ / (サンプルレート * チャンネル数 * ビット深度/8)
        bytes_per_sample = bits_per_sample // 8
        duration = data_size / (sample_rate * channels * bytes_per_sample)
        return round(duration, 2)
    except Exception as e:
        logger.warning(f"Failed to calculate WAV duration: {e}")
        return 0.0


@router.post("/generate", response_model=TTSResponse)
async def generate_speech(request: TTSRequest):
    """
    テキストから音声を生成する

    VOICEVOX APIを使用して日本語テキストをWAV音声に変換する。

    - text: 音声に変換するテキスト
    - speaker_id: VOICEVOX話者ID（デフォルト: 3 = ずんだもん）

    話者ID一覧（一部）:
    - 0: 四国めたん（あまあま）
    - 1: ずんだもん（あまあま）
    - 2: 四国めたん（ノーマル）
    - 3: ずんだもん（ノーマル）
    - 8: 春日部つむぎ
    """
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Step 1: audio_query で音声クエリを生成
            query_response = await client.post(
                f"{VOICEVOX_HOST}/audio_query",
                params={
                    "text": request.text,
                    "speaker": request.speaker_id,
                },
            )

            if query_response.status_code != 200:
                logger.error(f"VOICEVOX audio_query failed: {query_response.text}")
                raise HTTPException(
                    status_code=502,
                    detail=f"VOICEVOX audio_query failed: {query_response.status_code}"
                )

            audio_query = query_response.json()

            # Step 2: synthesis で音声合成
            synthesis_response = await client.post(
                f"{VOICEVOX_HOST}/synthesis",
                params={"speaker": request.speaker_id},
                json=audio_query,
            )

            if synthesis_response.status_code != 200:
                logger.error(f"VOICEVOX synthesis failed: {synthesis_response.text}")
                raise HTTPException(
                    status_code=502,
                    detail=f"VOICEVOX synthesis failed: {synthesis_response.status_code}"
                )

            # WAVデータを取得
            wav_data = synthesis_response.content

            # Base64エンコード
            audio_base64 = base64.b64encode(wav_data).decode("utf-8")

            # 再生時間を計算
            duration_seconds = calculate_wav_duration(wav_data)

            return TTSResponse(
                audio_base64=audio_base64,
                duration_seconds=duration_seconds,
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
        logger.exception(f"TTS generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {str(e)}")


@router.get("/speakers")
async def get_speakers():
    """
    利用可能な話者一覧を取得する
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{VOICEVOX_HOST}/speakers")

            if response.status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail=f"VOICEVOX speakers API failed: {response.status_code}"
                )

            return response.json()

    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to VOICEVOX. Please ensure VOICEVOX is running at {VOICEVOX_HOST}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get speakers: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get speakers: {str(e)}")


@router.get("/health")
async def tts_health_check():
    """
    TTSサービスのヘルスチェック
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{VOICEVOX_HOST}/version")

            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "voicevox_version": response.text.strip('"'),
                    "voicevox_host": VOICEVOX_HOST,
                }
            else:
                return {
                    "status": "unhealthy",
                    "error": f"VOICEVOX returned status {response.status_code}",
                    "voicevox_host": VOICEVOX_HOST,
                }

    except httpx.ConnectError:
        return {
            "status": "unhealthy",
            "error": "Cannot connect to VOICEVOX",
            "voicevox_host": VOICEVOX_HOST,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "voicevox_host": VOICEVOX_HOST,
        }
