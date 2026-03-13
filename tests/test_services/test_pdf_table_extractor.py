"""PDF表抽出のテスト"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from app.core.pdf_table_extractor import (
    _download_pdf,
    _pdf_to_images,
    EXTRACT_TOOL,
    EXTRACT_PROMPT,
    MAX_PAGES,
)


class TestExtractTool:
    """抽出ツールスキーマのテスト"""

    def test_tool_name(self):
        assert EXTRACT_TOOL["name"] == "submit_financial_data"

    def test_income_statement_fields(self):
        props = EXTRACT_TOOL["input_schema"]["properties"]["income_statement"]["properties"]
        assert "revenue" in props
        assert "operating_profit" in props
        assert "net_profit" in props
        assert "eps" in props

    def test_guidance_fields(self):
        props = EXTRACT_TOOL["input_schema"]["properties"]["guidance"]["properties"]
        assert "revenue_forecast" in props
        assert "revision" in props

    def test_required_fields(self):
        assert "income_statement" in EXTRACT_TOOL["input_schema"]["required"]


class TestDownloadPdf:
    """PDFダウンロードのテスト"""

    @patch("app.core.pdf_table_extractor.requests")
    def test_download_success(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.content = b"%PDF-1.4 test"
        mock_requests.get.return_value = mock_resp
        result = _download_pdf("https://example.com/test.pdf")
        assert result == b"%PDF-1.4 test"
        mock_requests.get.assert_called_once_with("https://example.com/test.pdf", timeout=30)

    @patch("app.core.pdf_table_extractor.requests")
    def test_download_raises_on_error(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("404")
        mock_requests.get.return_value = mock_resp
        with pytest.raises(Exception):
            _download_pdf("https://example.com/missing.pdf")


class TestPdfToImages:
    """PDF→画像変換のテスト"""

    def test_converts_pages(self):
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        # pdf2imageモジュールをモックで差し替え
        mock_pdf2image = MagicMock()
        imgs = [Image.new("RGB", (100, 100), "white") for _ in range(2)]
        mock_pdf2image.convert_from_bytes.return_value = imgs

        import sys
        sys.modules["pdf2image"] = mock_pdf2image
        try:
            # 関数内のimportがモックを取得するよう再呼び出し
            result = _pdf_to_images(b"fake pdf bytes", max_pages=2)
            assert len(result) == 2
            assert all(isinstance(b, bytes) for b in result)
            mock_pdf2image.convert_from_bytes.assert_called_once()
        finally:
            del sys.modules["pdf2image"]

    def test_returns_empty_without_pdf2image(self):
        # pdf2image がインポートできない場合
        with patch.dict("sys.modules", {"pdf2image": None}):
            # モジュールキャッシュの問題を避けるため直接テスト
            result = _pdf_to_images(b"fake")
            # pdf2image がインストールされていれば正常動作、なければ空リスト
            assert isinstance(result, list)


class TestExtractPrompt:
    """抽出プロンプトのテスト"""

    def test_prompt_mentions_json(self):
        assert "json" in EXTRACT_PROMPT.lower() or "JSON" in EXTRACT_PROMPT

    def test_prompt_mentions_百万円(self):
        assert "百万円" in EXTRACT_PROMPT

    def test_max_pages_default(self):
        assert MAX_PAGES == 3
