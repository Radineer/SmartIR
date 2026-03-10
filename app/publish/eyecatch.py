"""Generate OGP eyecatch images for note.com articles using Playwright.

Renders an HTML template to a 1280x670px PNG screenshot with Iris brand styling.
Adapted from boatrace-ai's eyecatch.py.
"""

from __future__ import annotations

import logging
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

    subtitle_html = ""
    if subtitle:
        subtitle_html = (
            f'<div style="font-size: 24px; color: {COLOR_CYAN}; '
            f'margin-top: 12px; letter-spacing: 2px;">{subtitle}</div>'
        )

    display_title = title
    if len(display_title) > 40:
        display_title = display_title[:40] + "..."

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    width: {WIDTH}px;
    height: {HEIGHT}px;
    background: linear-gradient(135deg, {COLOR_MAIN} 0%, {COLOR_BG} 100%);
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    font-family: "Hiragino Sans", "Hiragino Kaku Gothic ProN",
                 "Noto Sans JP", "Yu Gothic", sans-serif;
    overflow: hidden;
    position: relative;
  }}
  .accent-top {{
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 6px;
    background: linear-gradient(90deg, {COLOR_ACCENT}, {COLOR_CYAN}, transparent);
  }}
  .accent-bottom {{
    position: absolute;
    bottom: 0; left: 0; right: 0;
    height: 6px;
    background: linear-gradient(90deg, transparent, {COLOR_CYAN}, {COLOR_ACCENT});
  }}
  .icon {{
    font-size: 80px;
    margin-bottom: 20px;
    filter: drop-shadow(0 0 20px {icon_color}40);
  }}
  .title {{
    font-size: 42px;
    font-weight: 900;
    color: {COLOR_TEXT};
    text-align: center;
    padding: 0 80px;
    line-height: 1.4;
    max-width: 1100px;
    word-break: break-all;
  }}
  .brand {{
    position: absolute;
    bottom: 40px;
    right: 60px;
    font-size: 32px;
    font-weight: 700;
    color: {COLOR_ACCENT};
    letter-spacing: 4px;
  }}
  .brand-sub {{
    position: absolute;
    bottom: 80px;
    right: 60px;
    font-size: 16px;
    color: {COLOR_TEXT}80;
    letter-spacing: 2px;
  }}
  .grid-overlay {{
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    background-image:
      linear-gradient({COLOR_ACCENT}06 1px, transparent 1px),
      linear-gradient(90deg, {COLOR_ACCENT}06 1px, transparent 1px);
    background-size: 40px 40px;
    pointer-events: none;
  }}
  /* Iris character silhouette hint */
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
  <div class="accent-bottom"></div>
  <div class="grid-overlay"></div>
  <div class="icon">{icon_text}</div>
  <div class="title">{display_title}</div>
  {subtitle_html}
  <div class="iris-accent">Powered by Iris \u2014 AI IR Analyst</div>
  <div class="brand-sub">AI-Powered IR Analysis</div>
  <div class="brand">SmartIR</div>
</body>
</html>"""


async def generate_eyecatch(
    title: str,
    article_type: str = "analysis",
    subtitle: str | None = None,
) -> Path | None:
    """Generate an OGP eyecatch image using Playwright.

    Args:
        title: Article title to display on the image.
        article_type: One of breaking, analysis, daily_summary, industry,
                      weekly_trend, earnings_calendar.
        subtitle: Optional subtitle line.

    Returns:
        Path to the generated PNG file (in a temp directory), or None on failure.
    """
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
