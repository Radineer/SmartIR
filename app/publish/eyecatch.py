"""Generate OGP eyecatch images for note.com articles using Playwright.

Renders an HTML template to a 1280x670px PNG screenshot with Iris brand styling.
Supports Gemini AI image generation with HTML fallback.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)

# Iris brand colors (from character-iris.md)
COLOR_MAIN = "#1E1B4B"       # Midnight (dark bg)
COLOR_ACCENT = "#6366F1"     # Iris Blue
COLOR_CYAN = "#22D3EE"       # Cyber Cyan
COLOR_AMBER = "#F59E0B"      # Amber (warning/breaking)
COLOR_TEXT = "#E5E7EB"        # Silver
COLOR_BG = "#0F0D2E"         # Deeper midnight

# Article type -> (icon, color)
ARTICLE_ICONS: dict[str, tuple[str, str]] = {
    "breaking":          ("\u26a1", COLOR_AMBER),    # ⚡
    "analysis":          ("\U0001f4ca", COLOR_ACCENT),  # 📊
    "daily_summary":     ("\U0001f4c5", COLOR_CYAN),    # 📅
    "industry":          ("\U0001f50d", COLOR_ACCENT),   # 🔍
    "weekly_trend":      ("\U0001f4c8", COLOR_CYAN),     # 📈
    "earnings_calendar": ("\U0001f5d3", COLOR_AMBER),    # 🗓
}

# Article type -> badge label
TYPE_LABELS: dict[str, str] = {
    "breaking":          "速報",
    "analysis":          "決算分析",
    "daily_summary":     "日次まとめ",
    "industry":          "業界分析",
    "weekly_trend":      "週次トレンド",
    "earnings_calendar": "決算カレンダー",
}

# OGP image dimensions (note.com recommended)
WIDTH = 1280
HEIGHT = 670



def _build_eyecatch_html(
    title: str,
    article_type: str = "analysis",
    subtitle: str | None = None,
    company_name: str | None = None,
    key_metric: str | None = None,
    sentiment: str | None = None,
) -> str:
    """Build eyecatch HTML - clean, bright, note-friendly design."""

    # Color scheme based on sentiment
    if sentiment == "positive":
        accent = "#059669"      # Green
        accent_bg = "#ECFDF5"   # Light green bg
        badge_text = "好決算"
        badge_emoji = "\u2191"  # ↑
    elif sentiment == "negative":
        accent = "#DC2626"      # Red
        accent_bg = "#FEF2F2"   # Light red bg
        badge_text = "要注目"
        badge_emoji = "\u2193"  # ↓
    else:
        accent = "#2563EB"      # Blue
        accent_bg = "#EFF6FF"   # Light blue bg
        badge_text = "決算分析"
        badge_emoji = ""

    # Article type overrides
    type_config = {
        "breaking":          ("速報", "#F59E0B", "#FFFBEB"),
        "daily_summary":     ("決算まとめ", "#7C3AED", "#F5F3FF"),
        "weekly_trend":      ("週次レポート", "#0891B2", "#ECFEFF"),
        "industry":          ("業界分析", "#4F46E5", "#EEF2FF"),
        "earnings_calendar": ("決算カレンダー", "#D97706", "#FFFBEB"),
        "trading_challenge": ("運用日誌", "#059669", "#ECFDF5"),
    }
    if article_type in type_config:
        badge_text, accent, accent_bg = type_config[article_type]

    # Display elements
    display_title = title.replace(" - SmartIR", "").strip()
    if len(display_title) > 40:
        display_title = display_title[:40] + "..."

    company_html = ""
    if company_name:
        company_html = f'''<div style="font-size: 22px; color: #6B7280; font-weight: 500;
            letter-spacing: 1px; margin-bottom: 8px;">{company_name}</div>'''

    metric_html = ""
    if key_metric:
        metric_html = f'''<div style="font-size: 28px; color: {accent}; font-weight: 800;
            margin-top: 16px; letter-spacing: 0.5px;">{key_metric}</div>'''

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700;900&display=swap');
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    width: {WIDTH}px;
    height: {HEIGHT}px;
    background: #FFFFFF;
    display: flex;
    font-family: "Noto Sans JP", "Hiragino Sans", sans-serif;
    overflow: hidden;
    position: relative;
  }}
  .left {{
    width: 70%;
    padding: 60px 50px 60px 70px;
    display: flex;
    flex-direction: column;
    justify-content: center;
  }}
  .right {{
    width: 30%;
    background: {accent_bg};
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    position: relative;
  }}
  .right::before {{
    content: "";
    position: absolute;
    left: 0; top: 80px; bottom: 80px;
    width: 3px;
    background: {accent};
    border-radius: 2px;
  }}
  .badge {{
    display: inline-block;
    padding: 6px 20px;
    background: {accent};
    color: white;
    font-size: 16px;
    font-weight: 700;
    border-radius: 4px;
    letter-spacing: 2px;
    margin-bottom: 20px;
    width: fit-content;
  }}
  .title {{
    font-size: 36px;
    font-weight: 900;
    color: #111827;
    line-height: 1.5;
    letter-spacing: -0.5px;
  }}
  .brand {{
    font-size: 28px;
    font-weight: 900;
    color: {accent};
    letter-spacing: 3px;
  }}
  .brand-sub {{
    font-size: 13px;
    color: #9CA3AF;
    letter-spacing: 2px;
    margin-top: 4px;
  }}
  .accent-bar {{
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 6px;
    background: {accent};
  }}
</style>
</head>
<body>
  <div class="accent-bar"></div>
  <div class="left">
    <div class="badge">{badge_emoji} {badge_text}</div>
    {company_html}
    <div class="title">{display_title}</div>
    {metric_html}
  </div>
  <div class="right">
    <div class="brand">SmartIR</div>
    <div class="brand-sub">EARNINGS ANALYSIS</div>
  </div>
</body>
</html>"""



# ── Gemini AI image generation prompts ────────────────────────

GEMINI_PROMPTS: dict[str, str] = {
    "analysis": (
        "A futuristic financial analysis dashboard with holographic charts "
        "and data visualizations floating in dark space. Glowing indigo and "
        "cyan color palette, clean modern aesthetic, no text."
    ),
    "breaking": (
        "A dramatic newsroom scene with digital displays showing breaking "
        "financial news, urgent atmosphere with amber and indigo lighting, "
        "futuristic corporate setting, no text."
    ),
    "daily_summary": (
        "An elegant overview of Tokyo financial district at dusk, with "
        "holographic data overlays showing market trends, cool blue and "
        "purple tones, sophisticated atmosphere, no text."
    ),
    "weekly_trend": (
        "A futuristic holographic dashboard floating in dark space, "
        "showing glowing trend charts and graphs in indigo and cyan colors. "
        "Clean, modern, data science aesthetic, no text."
    ),
    "industry": (
        "A sophisticated comparison visualization of multiple companies, "
        "with interconnected data nodes and flowing data streams in indigo "
        "and cyan, abstract corporate art style, no text."
    ),
    "earnings_calendar": (
        "An elegant digital calendar with glowing entries and financial "
        "icons, futuristic corporate planning aesthetic with amber and "
        "indigo highlights, no text."
    ),
}


async def generate_gemini_eyecatch(
    title: str,
    article_type: str = "analysis",
    subtitle: str | None = None,
) -> Path | None:
    """Generate an eyecatch image using Google Gemini image generation.

    Returns Path to the generated PNG file, or None if unavailable/failed.
    """
    google_api_key = os.getenv("GOOGLE_API_KEY")
    gemini_enabled = os.getenv("GEMINI_EYECATCH_ENABLED", "false").lower() == "true"

    if not google_api_key or not gemini_enabled:
        return None

    try:
        from google import genai
    except ImportError:
        log.warning("google-genai が未インストールのためGemini画像生成をスキップ")
        return None

    base_prompt = GEMINI_PROMPTS.get(article_type, GEMINI_PROMPTS["analysis"])
    display_title = title.replace(" - SmartIR", "")
    prompt = (
        f"{base_prompt} "
        f"The theme of this image is related to: {display_title}"
    )

    try:
        gemini_model = os.getenv("GEMINI_IMAGE_MODEL", "imagen-3.0-generate-002")
        client = genai.Client(api_key=google_api_key)
        response = client.models.generate_images(
            model=gemini_model,
            prompt=prompt,
            config=genai.types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="16:9",
            ),
        )

        if not response.generated_images:
            log.warning("Gemini画像生成: 画像が返されませんでした")
            return None

        image_bytes = response.generated_images[0].image.image_bytes

        tmp_dir = tempfile.mkdtemp(prefix="eyecatch_gemini_")
        png_path = Path(tmp_dir) / "eyecatch.png"
        png_path.write_bytes(image_bytes)
        log.info("Gemini eyecatch generated: %s", png_path)
        return png_path

    except Exception as e:
        log.warning("Gemini画像生成に失敗 (HTML方式にフォールバック): %s", e)
        return None


async def generate_eyecatch(
    title: str,
    article_type: str = "analysis",
    subtitle: str | None = None,
    company_name: str | None = None,
    key_metric: str | None = None,
    sentiment: str | None = None,
) -> Path | None:
    """Generate an OGP eyecatch image.

    First attempts Gemini AI image generation. Falls back to HTML+Playwright
    if Gemini is unavailable or fails.

    Returns Path to the generated PNG file, or None on failure.
    """
    # Try Gemini first
    gemini_path = await generate_gemini_eyecatch(title, article_type, subtitle)
    if gemini_path:
        return gemini_path

    # Fallback: HTML → Playwright
    return await _generate_html_eyecatch(title, article_type, subtitle, company_name, key_metric, sentiment)


async def _generate_html_eyecatch(
    title: str,
    article_type: str = "analysis",
    subtitle: str | None = None,
    company_name: str | None = None,
    key_metric: str | None = None,
    sentiment: str | None = None,
) -> Path | None:
    """Generate an OGP eyecatch image using HTML + Playwright (fallback)."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log.warning("playwright が未インストールのためアイキャッチ生成をスキップ")
        return None

    html_content = _build_eyecatch_html(title, article_type, subtitle, company_name, key_metric, sentiment)

    tmp_dir = tempfile.mkdtemp(prefix="eyecatch_")
    html_path = Path(tmp_dir) / "eyecatch.html"
    png_path = Path(tmp_dir) / "eyecatch.png"
    html_path.write_text(html_content, encoding="utf-8")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox"],
            )
            try:
                page = await browser.new_page(
                    viewport={"width": WIDTH, "height": HEIGHT},
                )
                await page.goto(f"file://{html_path}")
                await page.screenshot(path=str(png_path), type="png")
                log.info("Eyecatch generated: %s", png_path)
                return png_path
            finally:
                await browser.close()
    except Exception as e:
        log.error("アイキャッチ画像の生成に失敗: %s", e)
        return None
