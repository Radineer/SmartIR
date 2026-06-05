"""
YouTube サムネイル自動生成モジュール

Pillow ベースでテンプレートからサムネイル画像（1280x720）を生成する。
スタイルプリセット: morning_market, ir_analysis, weekly_summary
"""

from __future__ import annotations

import logging
import os
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WIDTH = 1280
HEIGHT = 720

# プロジェクトルート（app/services/thumbnail_generator.py → ../../）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CHARACTER_IMAGE_DIR = PROJECT_ROOT / "frontend" / "public" / "images" / "iris"
DEFAULT_CHARACTER_IMAGE = CHARACTER_IMAGE_DIR / "iris-normal.png"
THUMBNAIL_OUTPUT_DIR = Path(os.getenv("THUMBNAIL_OUTPUT_DIR", "./static/thumbnails"))

# スタイルプリセット: (top_color, bottom_color)
STYLE_PRESETS: dict[str, dict] = {
    "morning_market": {
        "gradient_top": (26, 26, 46),       # #1a1a2e
        "gradient_bottom": (15, 52, 96),     # #0f3460
        "accent_color": (59, 130, 246),      # blue accent
        "label": "朝の市況",
        "show_grid": True,
    },
    "ir_analysis": {
        "gradient_top": (26, 26, 46),        # #1a1a2e
        "gradient_bottom": (83, 52, 131),    # #533483
        "accent_color": (168, 85, 247),      # purple accent
        "label": "IR分析",
        "show_grid": False,
    },
    "weekly_summary": {
        "gradient_top": (26, 26, 46),        # #1a1a2e
        "gradient_bottom": (27, 67, 50),     # #1b4332
        "accent_color": (34, 197, 94),       # green accent
        "label": "週間まとめ",
        "show_grid": False,
    },
}

# センチメント表示設定
SENTIMENT_CONFIG = {
    "positive": {"symbol": "▲", "color": (34, 197, 94), "label": "ポジティブ"},
    "negative": {"symbol": "▼", "color": (239, 68, 68), "label": "ネガティブ"},
    "neutral":  {"symbol": "●", "color": (156, 163, 175), "label": "ニュートラル"},
}

# ---------------------------------------------------------------------------
# Font discovery
# ---------------------------------------------------------------------------

# macOS / Linux で日本語フォントを探す候補パス
_FONT_SEARCH_PATHS: list[str] = [
    # macOS
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "/System/Library/Fonts/Supplemental/Hiragino Sans W6.ttc",
    "/System/Library/Fonts/Supplemental/Hiragino Sans W3.ttc",
    "/Library/Fonts/NotoSansCJKjp-Bold.otf",
    "/Library/Fonts/NotoSansCJKjp-Regular.otf",
    "/Library/Fonts/NotoSansJP-Bold.ttf",
    "/Library/Fonts/NotoSansJP-Regular.ttf",
    # Linux
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJKjp-Bold.otf",
    "/usr/share/fonts/noto-cjk/NotoSansCJKjp-Regular.otf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/google-noto-cjk/NotoSansCJKjp-Bold.otf",
]


def _find_system_font() -> str | None:
    """利用可能な日本語フォントをシステムから探す。"""
    for p in _FONT_SEARCH_PATHS:
        if Path(p).exists():
            return p
    return None


def _load_font(font_path: str | None, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """フォントをロードする。見つからない場合は Pillow デフォルトにフォールバック。"""
    if font_path and Path(font_path).exists():
        try:
            return ImageFont.truetype(font_path, size)
        except Exception as e:
            logger.warning(f"Failed to load font {font_path}: {e}")

    # フォールバック: Pillow デフォルト
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        # 古い Pillow ではサイズ指定不可
        return ImageFont.load_default()


# ---------------------------------------------------------------------------
# ThumbnailGenerator
# ---------------------------------------------------------------------------


class ThumbnailGenerator:
    """YouTube サムネイル画像ジェネレーター"""

    def __init__(self, font_path: str | None = None):
        """
        Args:
            font_path: TrueType/OpenType フォントのパス。None なら自動検出。
        """
        self.font_path = font_path or _find_system_font()
        if self.font_path:
            logger.info(f"Thumbnail font: {self.font_path}")
        else:
            logger.warning("No Japanese font found; falling back to Pillow default")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        title: str,
        style: str = "morning_market",
        company_name: str | None = None,
        ticker_code: str | None = None,
        sentiment: str | None = None,
        date_str: str | None = None,
        output_path: str | None = None,
    ) -> str:
        """
        サムネイル画像を生成する。

        Args:
            title: メインタイトル（例: "朝の市況サマリー"）
            style: スタイルプリセット名
            company_name: 企業名（任意）
            ticker_code: 証券コード（任意）
            date_str: 日付文字列（任意、None なら今日の日付）
            sentiment: "positive" / "negative" / "neutral"（任意）
            output_path: 出力ファイルパス（任意、None なら自動生成）

        Returns:
            str: 出力ファイルの絶対パス
        """
        if date_str is None:
            date_str = datetime.now().strftime("%Y/%m/%d")

        if style not in STYLE_PRESETS:
            logger.warning(f"Unknown style '{style}', falling back to 'morning_market'")
            style = "morning_market"

        # 出力パスを決定
        if output_path is None:
            THUMBNAIL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(THUMBNAIL_OUTPUT_DIR / f"thumb_{style}_{ts}.png")

        # 画像を生成
        img = Image.new("RGB", (WIDTH, HEIGHT))

        self._draw_background(img, style)
        self._draw_style_label(img, style)
        self._draw_text(img, title, company_name, ticker_code, date_str)

        if sentiment:
            self._draw_sentiment(img, sentiment)

        self._overlay_character(img)

        # 保存
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, "PNG", quality=95)
        logger.info(f"Thumbnail saved: {output_path}")
        return output_path

    # ------------------------------------------------------------------
    # Background
    # ------------------------------------------------------------------

    def _draw_background(self, img: Image.Image, style: str) -> None:
        """グラデーション背景を描画する。"""
        preset = STYLE_PRESETS[style]
        top = preset["gradient_top"]
        bottom = preset["gradient_bottom"]
        draw = ImageDraw.Draw(img)

        for y in range(HEIGHT):
            ratio = y / HEIGHT
            r = int(top[0] + (bottom[0] - top[0]) * ratio)
            g = int(top[1] + (bottom[1] - top[1]) * ratio)
            b = int(top[2] + (bottom[2] - top[2]) * ratio)
            draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))

        # グリッドパターン（morning_market のみ）
        if preset.get("show_grid"):
            grid_color = (*top, 30)  # 半透明
            overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
            grid_draw = ImageDraw.Draw(overlay)
            for x in range(0, WIDTH, 60):
                grid_draw.line([(x, 0), (x, HEIGHT)], fill=grid_color, width=1)
            for y in range(0, HEIGHT, 60):
                grid_draw.line([(0, y), (WIDTH, y)], fill=grid_color, width=1)
            img.paste(Image.alpha_composite(
                img.convert("RGBA"), overlay
            ).convert("RGB"))

        # 底部にアクセントライン
        accent = preset["accent_color"]
        draw = ImageDraw.Draw(img)
        draw.rectangle([(0, HEIGHT - 6), (WIDTH, HEIGHT)], fill=accent)

    # ------------------------------------------------------------------
    # Style label (top-left badge)
    # ------------------------------------------------------------------

    def _draw_style_label(self, img: Image.Image, style: str) -> None:
        """左上にスタイルラベルバッジを描画する。"""
        preset = STYLE_PRESETS[style]
        label = preset["label"]
        accent = preset["accent_color"]

        draw = ImageDraw.Draw(img)
        font = _load_font(self.font_path, 28)

        bbox = draw.textbbox((0, 0), label, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        pad_x, pad_y = 16, 8
        badge_x, badge_y = 40, 36
        draw.rounded_rectangle(
            [
                (badge_x, badge_y),
                (badge_x + text_w + pad_x * 2, badge_y + text_h + pad_y * 2),
            ],
            radius=8,
            fill=accent,
        )
        draw.text(
            (badge_x + pad_x, badge_y + pad_y),
            label,
            fill=(255, 255, 255),
            font=font,
        )

    # ------------------------------------------------------------------
    # Text overlays
    # ------------------------------------------------------------------

    def _draw_text(
        self,
        img: Image.Image,
        title: str,
        company_name: str | None,
        ticker_code: str | None,
        date_str: str,
    ) -> None:
        """タイトル・企業名・日付を描画する。"""
        draw = ImageDraw.Draw(img)

        # テキスト領域: 左側 60% （右側にキャラクター）
        text_area_width = int(WIDTH * 0.60)
        left_margin = 50
        max_chars = 14  # 折り返し文字数

        # --- Title (large, white, bold) ---
        title_font = _load_font(self.font_path, 56)
        wrapped_title = textwrap.fill(title, width=max_chars)
        title_y = 110
        draw.multiline_text(
            (left_margin, title_y),
            wrapped_title,
            fill=(255, 255, 255),
            font=title_font,
            spacing=12,
        )

        # タイトルの高さを計算
        title_bbox = draw.multiline_textbbox(
            (left_margin, title_y), wrapped_title, font=title_font, spacing=12
        )
        current_y = title_bbox[3] + 24

        # --- Company name (medium, yellow) ---
        if company_name:
            company_font = _load_font(self.font_path, 38)
            display_name = company_name
            if ticker_code:
                display_name = f"{company_name}（{ticker_code}）"
            wrapped_company = textwrap.fill(display_name, width=18)
            draw.multiline_text(
                (left_margin, current_y),
                wrapped_company,
                fill=(253, 224, 71),  # yellow-300
                font=company_font,
                spacing=8,
            )
            company_bbox = draw.multiline_textbbox(
                (left_margin, current_y), wrapped_company, font=company_font, spacing=8
            )
            current_y = company_bbox[3] + 16

        # --- Date (small, gray) ---
        date_font = _load_font(self.font_path, 28)
        # 日付は下部に固定
        date_y = HEIGHT - 60
        draw.text(
            (left_margin, date_y),
            date_str,
            fill=(156, 163, 175),  # gray-400
            font=date_font,
        )

        # --- "イリスのIR分析" ブランドテキスト ---
        brand_font = _load_font(self.font_path, 22)
        draw.text(
            (left_margin, date_y - 34),
            "イリスのIR分析",
            fill=(107, 114, 128),  # gray-500
            font=brand_font,
        )

    # ------------------------------------------------------------------
    # Sentiment indicator
    # ------------------------------------------------------------------

    def _draw_sentiment(self, img: Image.Image, sentiment: str) -> None:
        """センチメントインジケーター（矢印）を描画する。"""
        config = SENTIMENT_CONFIG.get(sentiment)
        if not config:
            logger.warning(f"Unknown sentiment: {sentiment}")
            return

        draw = ImageDraw.Draw(img)

        # 左下付近（日付の上、ブランドテキストの上）
        indicator_x = int(WIDTH * 0.35)
        indicator_y = HEIGHT - 100

        # シンボル
        symbol_font = _load_font(self.font_path, 64)
        draw.text(
            (indicator_x, indicator_y - 20),
            config["symbol"],
            fill=config["color"],
            font=symbol_font,
        )

        # ラベル
        label_font = _load_font(self.font_path, 26)
        draw.text(
            (indicator_x + 70, indicator_y),
            config["label"],
            fill=config["color"],
            font=label_font,
        )

    # ------------------------------------------------------------------
    # Character overlay
    # ------------------------------------------------------------------

    def _overlay_character(
        self, img: Image.Image, character_path: str | None = None
    ) -> None:
        """右側にイリスキャラクター画像をオーバーレイする。"""
        # 候補パスを探す
        candidates = []
        if character_path:
            candidates.append(Path(character_path))
        candidates.extend([
            CHARACTER_IMAGE_DIR / "iris-thumbnail.png",
            DEFAULT_CHARACTER_IMAGE,
            CHARACTER_IMAGE_DIR / "iris-happy.png",
        ])

        char_img = None
        for p in candidates:
            if p.exists():
                try:
                    char_img = Image.open(p).convert("RGBA")
                    logger.debug(f"Character image loaded: {p}")
                    break
                except Exception as e:
                    logger.warning(f"Failed to load character image {p}: {e}")

        if char_img is None:
            logger.info("No character image found; skipping overlay")
            return

        # キャラクターを右側に配置（高さ 85% にリサイズ）
        target_h = int(HEIGHT * 0.85)
        aspect = char_img.width / char_img.height
        target_w = int(target_h * aspect)
        char_img = char_img.resize((target_w, target_h), Image.LANCZOS)

        # 右端に配置
        paste_x = WIDTH - target_w - 20
        paste_y = HEIGHT - target_h

        # RGBA で合成
        rgba_img = img.convert("RGBA")
        rgba_img.paste(char_img, (paste_x, paste_y), char_img)
        img.paste(rgba_img.convert("RGB"))
