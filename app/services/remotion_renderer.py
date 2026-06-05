"""
Remotion ビデオレンダラー

broadcast_scheduler や short_video_generator から呼び出し、
Remotion CLI を使って高品質な動画を生成する。

ffmpeg 直出しの紙芝居品質 → Remotion の VRM アニメーション＋チャート＋字幕品質へ。
"""

import json
import logging
import os
import subprocess
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
DEFAULT_OUTPUT_DIR = Path(os.getenv("VIDEO_OUTPUT_DIR", str(PROJECT_ROOT / "static" / "videos")))

# Remotion composition settings
FPS = 30
OP_FRAMES = 150   # 5秒
ED_FRAMES = 240   # 8秒


class RemotionRenderer:
    """Remotion CLI を使った高品質動画レンダリング"""

    def __init__(self, frontend_dir: str | None = None):
        self.frontend_dir = Path(frontend_dir) if frontend_dir else FRONTEND_DIR
        self.entry_point = self.frontend_dir / "src" / "remotion" / "index.ts"

    def is_available(self) -> bool:
        """Remotion が利用可能か確認（node_modules + npx）"""
        remotion_pkg = self.frontend_dir / "node_modules" / "remotion"
        if not remotion_pkg.exists():
            logger.warning("Remotion not installed. Run 'npm install' in frontend/")
            return False
        if not shutil.which("npx"):
            logger.warning("npx not found in PATH")
            return False
        return True

    def render(
        self,
        title: str,
        script_segments: list[dict],
        audio_path: str | None = None,
        bgm_path: str | None = None,
        output_path: str | None = None,
        company_name: str = "AI-IR Insight",
        use_vrm: bool = True,
        character_image: str | None = None,
        composition_id: str = "IRAnalysis",
        concurrency: int = 4,
        crf: int = 23,
    ) -> str:
        """
        Remotion で動画をレンダリング

        Args:
            title: 動画タイトル
            script_segments: セグメント配列 [{"text", "startFrame", "durationFrames", "expression", ...}]
            audio_path: ナレーション音声パス（frontend/public/ からの相対パス or 絶対パス）
            bgm_path: BGMファイルパス
            output_path: 出力先パス
            company_name: 会社名表示
            use_vrm: VRM 3Dモデル使用
            character_image: キャラ画像パス（VRM不使用時）
            composition_id: Remotion composition ID
            concurrency: 並列レンダリングスレッド数
            crf: 品質（0-51, 低いほど高品質）

        Returns:
            出力ファイルパス
        """
        if not self.is_available():
            raise RuntimeError("Remotion is not available. Install dependencies first.")

        if output_path is None:
            DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            output_path = str(DEFAULT_OUTPUT_DIR / f"remotion_{title[:30].replace(' ', '_')}.mp4")

        # 音声ファイルをfrontend/public/ にコピー（Remotionからアクセスするため）
        audio_url = None
        if audio_path:
            audio_url = self._prepare_audio(audio_path)

        bgm_url = None
        if bgm_path:
            bgm_url = self._prepare_audio(bgm_path, prefix="bgm_")
        else:
            # デフォルトBGM
            default_bgm = self.frontend_dir / "public" / "audio" / "bgm" / "business-calm.mp3"
            if default_bgm.exists():
                bgm_url = "/audio/bgm/business-calm.mp3"

        # InputProps 構築
        input_props = {
            "title": title,
            "companyName": company_name,
            "script": script_segments,
            "useVRM": use_vrm,
        }
        if audio_url:
            input_props["audioUrl"] = audio_url
        if bgm_url:
            input_props["bgmUrl"] = bgm_url
        if character_image:
            input_props["characterImage"] = character_image
        if use_vrm:
            vrm_path = self.frontend_dir / "public" / "models" / "vrm" / "iris.vrm"
            if vrm_path.exists():
                input_props["vrmModelUrl"] = "/models/vrm/iris.vrm"

        # InputProps を一時ファイルに書き出し（コマンドライン長制限回避）
        props_file = Path(output_path).with_suffix(".props.json")
        with open(props_file, "w", encoding="utf-8") as f:
            json.dump(input_props, f, ensure_ascii=False)

        # Remotion CLI 実行
        cmd = [
            "npx", "remotion", "render",
            str(self.entry_point),
            composition_id,
            str(output_path),
            "--props", str(props_file),
            "--concurrency", str(concurrency),
            "--crf", str(crf),
            "--pixel-format", "yuv420p",
            "--codec", "h264",
            "--audio-codec", "aac",
            "--audio-bitrate", "192k",
            "--log", "warn",
        ]

        logger.info(f"Rendering with Remotion: {composition_id} → {output_path}")
        logger.info(f"  Title: {title}")
        logger.info(f"  Segments: {len(script_segments)}")
        logger.info(f"  VRM: {use_vrm}")

        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.frontend_dir),
                capture_output=True,
                text=True,
                timeout=600,  # 10分タイムアウト
            )

            if result.returncode != 0:
                logger.error(f"Remotion render failed (exit {result.returncode})")
                logger.error(f"stderr: {result.stderr[:2000]}")
                raise RuntimeError(f"Remotion render failed: {result.stderr[:500]}")

            logger.info(f"Remotion render complete: {output_path}")

            # 出力ファイル確認
            if not Path(output_path).exists():
                raise RuntimeError(f"Output file not created: {output_path}")

            return output_path

        except subprocess.TimeoutExpired:
            raise RuntimeError("Remotion render timed out (600s)")

        finally:
            # props ファイルクリーンアップ
            if props_file.exists():
                props_file.unlink()

    def _prepare_audio(self, audio_path: str, prefix: str = "render_") -> str:
        """
        音声ファイルを frontend/public/audio/ にコピーし、Remotion用相対パスを返す
        """
        src = Path(audio_path)
        if not src.exists():
            logger.warning(f"Audio file not found: {audio_path}")
            return ""

        dest_dir = self.frontend_dir / "public" / "audio" / "render"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{prefix}{src.name}"

        shutil.copy2(src, dest)
        return f"/audio/render/{prefix}{src.name}"


def build_script_segments(
    script_text: str,
    audio_segments: list[dict] | None = None,
    analysis_data: dict | None = None,
) -> list[dict]:
    """
    台本テキスト＋音声タイミングから Remotion ScriptSegment 配列を構築

    Args:
        script_text: 台本全文（セグメント分割はここで行う）
        audio_segments: TTS音声セグメント [{"text", "start", "duration"}]
        analysis_data: IR分析データ（AIAnalysis表示用）

    Returns:
        [{"text", "startFrame", "durationFrames", "expression", ...}]
    """
    import re

    segments = []

    if audio_segments:
        # TTS タイミングベース
        for i, seg in enumerate(audio_segments):
            start_sec = seg.get("start", 0)
            duration_sec = seg.get("duration", 3)
            text = seg.get("text", "")

            segment = {
                "text": text,
                "startFrame": OP_FRAMES + int(start_sec * FPS),
                "durationFrames": int(duration_sec * FPS),
                "expression": _detect_expression(text, i, len(audio_segments)),
            }

            # 分析モードセグメントにはAI分析データを添付
            if segment["expression"] == "ai_analysis" and analysis_data:
                segment["aiAnalysisData"] = _build_ai_analysis_data(analysis_data)
                segment["aiVisibleSections"] = ["sentiment", "scores", "insights", "risk"]

            segments.append(segment)
    else:
        # テキストベース（均等分割）
        lines = [line.strip() for line in script_text.split("\n") if line.strip()]
        # 空行区切りでセクション分割
        sections = re.split(r'\n\s*\n', script_text.strip())
        sentences = []
        for section in sections:
            sents = re.split(r'(?<=[。！？])', section.strip())
            sentences.extend([s.strip() for s in sents if s.strip()])

        total_duration_frames = 1800 - OP_FRAMES - ED_FRAMES  # OP/ED除外
        frames_per_sentence = max(total_duration_frames // max(len(sentences), 1), 60)

        current_frame = OP_FRAMES
        for i, sentence in enumerate(sentences):
            segments.append({
                "text": sentence,
                "startFrame": current_frame,
                "durationFrames": frames_per_sentence,
                "expression": _detect_expression(sentence, i, len(sentences)),
            })
            current_frame += frames_per_sentence

    return segments


def _detect_expression(text: str, index: int, total: int) -> str:
    """テキスト内容からキャラの表情を推定"""
    # 冒頭と末尾
    if index == 0:
        return "happy"
    if index >= total - 2:
        return "happy"

    # キーワードベース
    if any(w in text for w in ["分析", "センチメント", "リスク", "データ", "指標"]):
        return "ai_analysis"
    if any(w in text for w in ["注目", "重要", "ポイント", "急騰", "急落"]):
        return "surprised"
    if any(w in text for w in ["考え", "思い", "検討", "展望", "予想"]):
        return "thinking"
    if any(w in text for w in ["好調", "上昇", "改善", "好決算", "増収"]):
        return "confident"
    if any(w in text for w in ["懸念", "下落", "悪化", "減収", "リスク"]):
        return "concerned"

    return "neutral"


def _build_ai_analysis_data(analysis: dict) -> dict:
    """IR分析データをRemotionのAIAnalysisData形式に変換"""
    sentiment = analysis.get("sentiment", {})
    positive = sentiment.get("positive", 0.5) if isinstance(sentiment, dict) else 0.5
    negative = sentiment.get("negative", 0.3) if isinstance(sentiment, dict) else 0.3

    # センチメントスコア（0-100）
    sentiment_score = int(positive * 100)
    sentiment_label = "bullish" if positive > 0.6 else ("bearish" if negative > 0.5 else "neutral")

    key_points = analysis.get("key_points", [])
    if isinstance(key_points, str):
        import json as _json
        try:
            key_points = _json.loads(key_points)
        except Exception:
            key_points = [key_points]

    insights = []
    for i, point in enumerate(key_points[:5]):
        insights.append({
            "text": point if isinstance(point, str) else str(point),
            "priority": "high" if i == 0 else ("medium" if i < 3 else "low"),
        })

    return {
        "sentiment": sentiment_label,
        "sentimentScore": sentiment_score,
        "overallScore": min(sentiment_score + 10, 100),
        "fundamentalScore": sentiment_score,
        "technicalScore": max(sentiment_score - 5, 0),
        "newsSentimentScore": sentiment_score,
        "insights": insights,
        "riskLevel": "low" if positive > 0.7 else ("high" if negative > 0.5 else "medium"),
        "riskMessage": analysis.get("summary", "")[:100],
        "irisOpinion": analysis.get("summary", "データ分析中です…"),
    }
