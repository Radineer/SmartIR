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
    "analysis":          "AI分析",
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
) -> str:
    """Build HTML template for the eyecatch image."""
    icon_text, icon_color = ARTICLE_ICONS.get(
        article_type, ("\U0001f4ca", COLOR_ACCENT)
    )
    badge_text = TYPE_LABELS.get(article_type, "AI分析")

    subtitle_html = ""
    if subtitle:
        subtitle_html = (
            f'<div style="font-size: 24px; color: {COLOR_CYAN}; '
            f'margin-top: 12px; letter-spacing: 2px;">{subtitle}</div>'
        )

    # Smart title truncation
    display_title = title
    if " - SmartIR" in display_title:
        display_title = display_title.replace(" - SmartIR", "")
    if len(display_title) > 45:
        display_title = display_title[:45] + "..."

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    width: {WIDTH}px;
    height: {HEIGHT}px;
    background: linear-gradient(160deg, {COLOR_MAIN} 0%, #12103A 40%, {COLOR_BG} 100%);
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    font-family: "Hiragino Sans", "Hiragino Kaku Gothic ProN",
                 "Noto Sans JP", "Yu Gothic", sans-serif;
    overflow: hidden;
    position: relative;
  }}
  /* Accent bar at top */
  .accent-top {{
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 5px;
    background: linear-gradient(90deg, {COLOR_ACCENT}, {COLOR_CYAN}60, transparent);
  }}
  /* Wave decoration at bottom */
  .wave {{
    position: absolute;
    bottom: 0; left: 0; right: 0;
    height: 120px;
    opacity: 0.08;
  }}
  .wave svg {{
    width: 100%;
    height: 100%;
  }}
  /* Glow circle behind icon */
  .glow {{
    position: absolute;
    width: 200px;
    height: 200px;
    border-radius: 50%;
    background: radial-gradient(circle, {icon_color}18, transparent 70%);
    top: 50%;
    left: 50%;
    transform: translate(-50%, -65%);
    pointer-events: none;
  }}
  /* Badge */
  .badge {{
    display: inline-block;
    padding: 6px 24px;
    border: 1.5px solid {icon_color}90;
    border-radius: 4px;
    font-size: 18px;
    font-weight: 700;
    color: {icon_color};
    letter-spacing: 3px;
    margin-bottom: 24px;
    text-transform: uppercase;
  }}
  .icon {{
    font-size: 72px;
    color: {icon_color};
    margin-bottom: 16px;
    text-shadow: 0 0 40px {icon_color}30;
    position: relative;
    z-index: 1;
  }}
  .title {{
    font-size: 40px;
    font-weight: 900;
    color: {COLOR_TEXT};
    text-align: center;
    padding: 0 100px;
    line-height: 1.45;
    max-width: 1100px;
    word-break: break-all;
    position: relative;
    z-index: 1;
  }}
  .brand {{
    position: absolute;
    bottom: 30px;
    right: 50px;
    font-size: 36px;
    font-weight: 900;
    color: {COLOR_ACCENT};
    letter-spacing: 5px;
  }}
  .brand-sub {{
    position: absolute;
    bottom: 72px;
    right: 50px;
    font-size: 14px;
    color: {COLOR_TEXT}60;
    letter-spacing: 3px;
    text-transform: uppercase;
  }}
  /* Vertical accent line left */
  .side-line {{
    position: absolute;
    left: 40px;
    top: 60px;
    bottom: 60px;
    width: 3px;
    background: linear-gradient(180deg, {COLOR_ACCENT}40, transparent);
    border-radius: 2px;
  }}
  /* Subtle data grid */
  .grid-overlay {{
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    background-image:
      linear-gradient({COLOR_ACCENT}06 1px, transparent 1px),
      linear-gradient(90deg, {COLOR_ACCENT}06 1px, transparent 1px);
    background-size: 50px 50px;
    pointer-events: none;
  }}
  .iris-accent {{
    position: absolute;
    bottom: 40px;
    left: 60px;
    font-size: 14px;
    color: {COLOR_CYAN}60;
    letter-spacing: 1px;
  }}
</style>
</head>
<body>
  <div class="accent-top"></div>
  <div class="grid-overlay"></div>
  <div class="side-line"></div>
  <div class="glow"></div>
  <div class="wave">
    <svg viewBox="0 0 1280 120" preserveAspectRatio="none">
      <path d="M0,60 C320,120 640,0 960,60 C1120,90 1200,30 1280,60 L1280,120 L0,120 Z"
            fill="{COLOR_CYAN}" />
    </svg>
  </div>
  <div class="badge">{badge_text}</div>
  <div class="icon">{icon_text}</div>
  <div class="title">{display_title}</div>
  {subtitle_html}
  <div class="iris-accent">Powered by Iris \u2014 AI IR Analyst</div>
  <div class="brand-sub">AI-POWERED IR ANALYSIS</div>
  <div class="brand">SmartIR</div>
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
    return await _generate_html_eyecatch(title, article_type, subtitle)


async def _generate_html_eyecatch(
    title: str,
    article_type: str = "analysis",
    subtitle: str | None = None,
) -> Path | None:
    """Generate an OGP eyecatch image using HTML + Playwright (fallback)."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log.warning("playwright が未インストールのためアイキャッチ生成をスキップ")
        return None

    html_content = _build_eyecatch_html(title, article_type, subtitle)

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
