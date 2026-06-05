"""
マーケットコメンタリー音声生成スクリプト

market-commentary-script.json からテキストを読み込み、
AivisSpeech Engine でセグメント単位の音声を合成し、
結合WAVとセグメントタイミングJSONを出力する。
"""

import json
import io
import wave
import httpx
import time
from pathlib import Path

# 設定
AIVISSPEECH_HOST = "http://localhost:10101"
SPEAKER_ID = 1878365376  # コハク ノーマル（イリス用）
SILENCE_DURATION = 0.5  # セグメント間の無音（秒）

PROJECT_ROOT = Path(__file__).parent.parent
SCRIPT_PATH = PROJECT_ROOT / "frontend" / "src" / "data" / "market-commentary-script.json"
AUDIO_OUTPUT_DIR = PROJECT_ROOT / "frontend" / "public" / "audio"
SEGMENTS_OUTPUT = AUDIO_OUTPUT_DIR / "market-comment-full-segments.json"
COMBINED_OUTPUT = AUDIO_OUTPUT_DIR / "market-comment-full.wav"


def flatten_segments(script_data: dict) -> list[dict]:
    """台本JSONからフラットなセグメントリストを生成"""
    segments = []
    for section in script_data["segments"]:
        if "subsections" in section:
            for sub in section["subsections"]:
                segments.append({
                    "id": f"{section['id']}_{sub['id']}",
                    "title": sub["label"],
                    "text": sub["text"],
                    "expression": sub.get("expression", section.get("expression", "neutral")),
                })
        else:
            segments.append({
                "id": section["id"],
                "title": section["title"],
                "text": section["text"],
                "expression": section.get("expression", "neutral"),
            })
    return segments


def synthesize_segment(client: httpx.Client, text: str, speaker_id: int) -> bytes:
    """AivisSpeech で1セグメント分の音声を合成"""
    # audio_query
    resp = client.post(
        f"{AIVISSPEECH_HOST}/audio_query",
        params={"text": text, "speaker": speaker_id},
        timeout=60.0,
    )
    resp.raise_for_status()
    audio_query = resp.json()

    # 話速を少し調整（速すぎない程度に）
    audio_query["speedScale"] = 1.05
    audio_query["pitchScale"] = 0.0
    audio_query["volumeScale"] = 1.0

    # synthesis
    resp = client.post(
        f"{AIVISSPEECH_HOST}/synthesis",
        params={"speaker": speaker_id},
        json=audio_query,
        timeout=120.0,
    )
    resp.raise_for_status()
    return resp.content


def get_wav_duration(wav_data: bytes) -> float:
    """WAVデータの再生時間を計算"""
    buf = io.BytesIO(wav_data)
    with wave.open(buf, "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())


def concatenate_wavs(wav_list: list[bytes], silence_sec: float = 0.5) -> bytes:
    """複数のWAVデータを無音を挟んで結合"""
    if not wav_list:
        raise ValueError("Empty wav list")

    # 最初のWAVからパラメータ取得
    first = io.BytesIO(wav_list[0])
    with wave.open(first, "rb") as wf:
        n_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        frame_rate = wf.getframerate()

    silence_frames = int(frame_rate * silence_sec)
    silence_data = b"\x00" * (silence_frames * n_channels * sample_width)

    output = io.BytesIO()
    with wave.open(output, "wb") as out_wf:
        out_wf.setnchannels(n_channels)
        out_wf.setsampwidth(sample_width)
        out_wf.setframerate(frame_rate)

        for i, wav_data in enumerate(wav_list):
            buf = io.BytesIO(wav_data)
            with wave.open(buf, "rb") as wf:
                out_wf.writeframes(wf.readframes(wf.getnframes()))
            if i < len(wav_list) - 1:
                out_wf.writeframes(silence_data)

    return output.getvalue()


def main():
    # 台本読み込み
    print(f"Loading script: {SCRIPT_PATH}")
    with open(SCRIPT_PATH) as f:
        script_data = json.load(f)

    segments = flatten_segments(script_data)
    print(f"Total segments: {len(segments)}")

    # AivisSpeech接続確認
    print(f"Connecting to AivisSpeech: {AIVISSPEECH_HOST}")
    client = httpx.Client(timeout=120.0)

    try:
        version_resp = client.get(f"{AIVISSPEECH_HOST}/version")
        print(f"AivisSpeech version: {version_resp.text}")
    except Exception as e:
        print(f"ERROR: Cannot connect to AivisSpeech: {e}")
        print("Please run: docker compose up -d aivisspeech")
        return

    # スピーカー一覧を取得して確認
    try:
        speakers_resp = client.get(f"{AIVISSPEECH_HOST}/speakers")
        speakers = speakers_resp.json()
        print(f"Available speakers: {len(speakers)}")
        # SPEAKER_IDが有効か確認
        valid_ids = []
        for sp in speakers:
            for style in sp.get("styles", []):
                valid_ids.append(style["id"])
        if SPEAKER_ID not in valid_ids:
            print(f"WARNING: Speaker ID {SPEAKER_ID} not found. Available IDs: {valid_ids[:10]}...")
            # 最初のスピーカーにフォールバック
            if valid_ids:
                fallback_id = valid_ids[0]
                print(f"Falling back to speaker ID: {fallback_id}")
                global SPEAKER_ID_USED
                SPEAKER_ID_USED = fallback_id
            else:
                print("ERROR: No speakers available")
                return
        else:
            SPEAKER_ID_USED = SPEAKER_ID
            # スピーカー名を表示
            for sp in speakers:
                for style in sp.get("styles", []):
                    if style["id"] == SPEAKER_ID:
                        print(f"Using speaker: {sp['name']} ({style['name']}) ID={SPEAKER_ID}")
    except Exception as e:
        print(f"Could not verify speaker: {e}")
        SPEAKER_ID_USED = SPEAKER_ID

    # 各セグメントの音声合成
    AUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    wav_data_list = []
    segment_timings = []
    current_time = 0.0

    for i, seg in enumerate(segments):
        print(f"\n[{i+1}/{len(segments)}] {seg['id']}: {seg['text'][:40]}...")
        start = time.time()

        try:
            wav_data = synthesize_segment(client, seg["text"], SPEAKER_ID_USED)
            duration = get_wav_duration(wav_data)
            elapsed = time.time() - start
            print(f"  -> {duration:.3f}s audio, generated in {elapsed:.1f}s")

            # 個別WAVファイルを保存
            seg_filename = f"segment_{i:03d}_{seg['id']}.wav"
            seg_path = AUDIO_OUTPUT_DIR / seg_filename
            with open(seg_path, "wb") as f:
                f.write(wav_data)

            wav_data_list.append(wav_data)
            segment_timings.append({
                "index": i,
                "id": seg["id"],
                "title": seg["title"],
                "text": seg["text"],
                "start": round(current_time, 3),
                "end": round(current_time + duration, 3),
                "duration": round(duration, 3),
                "filename": seg_filename,
            })

            current_time += duration + SILENCE_DURATION

        except Exception as e:
            print(f"  ERROR: {e}")
            # エラーでも続行（タイミングは飛ばす）
            continue

    if not wav_data_list:
        print("\nERROR: No audio generated")
        return

    # WAVファイル結合
    print(f"\nConcatenating {len(wav_data_list)} segments...")
    combined = concatenate_wavs(wav_data_list, SILENCE_DURATION)
    total_duration = get_wav_duration(combined)

    # 結合WAVを保存
    with open(COMBINED_OUTPUT, "wb") as f:
        f.write(combined)
    print(f"Combined audio: {COMBINED_OUTPUT} ({total_duration:.3f}s)")

    # セグメントタイミングJSONを保存
    timing_data = {
        "speaker": "コハク",
        "speaker_id": SPEAKER_ID_USED,
        "total_duration": round(total_duration, 3),
        "segment_count": len(segment_timings),
        "segments": segment_timings,
    }
    with open(SEGMENTS_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(timing_data, f, ensure_ascii=False, indent=2)
    print(f"Segments JSON: {SEGMENTS_OUTPUT}")

    print(f"\nDone! Total duration: {total_duration:.1f}s ({len(segment_timings)} segments)")
    client.close()


if __name__ == "__main__":
    main()
