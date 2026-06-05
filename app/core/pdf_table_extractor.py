"""Claude Vision を使ったPDF表の構造化データ抽出。

決算短信の1-3ページ目を画像化し、Claude Visionに渡して
PL/BS/CF の数値を構造化JSONとして返す。
"""

from __future__ import annotations

import base64
import io
import logging
import os
import tempfile
from pathlib import Path

import requests

log = logging.getLogger(__name__)

# 抽出対象ページ数
MAX_PAGES = 3


def _download_pdf(url: str) -> bytes:
    """PDFをダウンロードしてバイト列を返す。"""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.content


def _pdf_to_images(pdf_bytes: bytes, max_pages: int = MAX_PAGES) -> list[bytes]:
    """PDFの先頭ページを画像(PNG)に変換。"""
    try:
        from pdf2image import convert_from_bytes
    except ImportError:
        log.warning("pdf2image が未インストール。pip install pdf2image")
        return []

    try:
        images = convert_from_bytes(
            pdf_bytes,
            first_page=1,
            last_page=max_pages,
            dpi=150,
            fmt="png",
        )
    except Exception as e:
        log.warning("PDF→画像変換に失敗: %s", e)
        return []

    result = []
    for img in images:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        result.append(buf.getvalue())

    return result


EXTRACT_PROMPT = """\
この画像は日本企業の決算短信のページです。
表形式の財務データを読み取り、以下のJSON構造で返してください。

```json
{
  "income_statement": {
    "revenue": null,
    "operating_profit": null,
    "ordinary_profit": null,
    "net_profit": null,
    "revenue_yoy": null,
    "op_yoy": null,
    "np_yoy": null,
    "eps": null
  },
  "guidance": {
    "revenue_forecast": null,
    "op_forecast": null,
    "np_forecast": null,
    "dividend_forecast": null,
    "revision": "none"
  },
  "fiscal_period": null,
  "fiscal_year": null,
  "unit": "百万円"
}
```

ルール:
- 数値は百万円単位に統一（千円表記なら÷1000）
- YoY(前年同期比)は%で記載
- 読み取れない値はnull
- revision: "up"/"down"/"unchanged"/"none"
- JSONのみ返してください（説明不要）
"""

EXTRACT_TOOL = {
    "name": "submit_financial_data",
    "description": "決算短信の表から抽出した財務データを構造化して提出",
    "input_schema": {
        "type": "object",
        "properties": {
            "income_statement": {
                "type": "object",
                "properties": {
                    "revenue": {"type": "number", "description": "売上高（百万円）"},
                    "operating_profit": {"type": "number", "description": "営業利益（百万円）"},
                    "ordinary_profit": {"type": "number", "description": "経常利益（百万円）"},
                    "net_profit": {"type": "number", "description": "純利益（百万円）"},
                    "revenue_yoy": {"type": "number", "description": "売上高YoY(%)"},
                    "op_yoy": {"type": "number", "description": "営業利益YoY(%)"},
                    "np_yoy": {"type": "number", "description": "純利益YoY(%)"},
                    "eps": {"type": "number", "description": "EPS(円)"},
                },
            },
            "guidance": {
                "type": "object",
                "properties": {
                    "revenue_forecast": {"type": "number"},
                    "op_forecast": {"type": "number"},
                    "np_forecast": {"type": "number"},
                    "dividend_forecast": {"type": "number"},
                    "revision": {"type": "string", "enum": ["up", "down", "unchanged", "none"]},
                },
            },
            "fiscal_period": {"type": "string", "description": "Q1/Q2/Q3/FY"},
            "fiscal_year": {"type": "string", "description": "e.g. 2026/3"},
            "unit": {"type": "string"},
        },
        "required": ["income_statement"],
    },
}


async def extract_financial_tables(pdf_url: str) -> dict | None:
    """PDFの表からClaude Visionで財務データを構造化抽出。

    Args:
        pdf_url: 決算短信PDFのURL

    Returns:
        構造化された財務データ dict、または失敗時 None
    """
    try:
        import anthropic
    except ImportError:
        log.warning("anthropic が未インストール")
        return None

    # 1. PDFダウンロード
    try:
        pdf_bytes = _download_pdf(pdf_url)
    except Exception as e:
        log.warning("PDF download failed: %s", e)
        return None

    # 2. 画像変換
    images = _pdf_to_images(pdf_bytes)
    if not images:
        log.warning("No images extracted from PDF")
        return None

    # 3. Claude Vision API
    model = os.getenv("SMARTIR_VISION_MODEL", "claude-sonnet-4-6")

    # 画像をbase64エンコード
    content = []
    for img_bytes in images:
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": b64,
            },
        })
    content.append({"type": "text", "text": EXTRACT_PROMPT})

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=model,
            max_tokens=2048,
            tools=[EXTRACT_TOOL],
            tool_choice={"type": "tool", "name": "submit_financial_data"},
            messages=[{"role": "user", "content": content}],
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_financial_data":
                log.info("Financial table extraction successful")
                return block.input

        log.warning("Vision response did not contain structured data")
        return None

    except Exception as e:
        log.error("Claude Vision extraction failed: %s", e)
        return None
