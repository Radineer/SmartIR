"""Tests for article generation."""

import pytest
from datetime import date
from unittest.mock import MagicMock

from app.publish.article import ArticleGenerator, ArticleContent


def _make_company(**kwargs):
    defaults = {
        "id": 1,
        "name": "テスト株式会社",
        "ticker_code": "1234",
        "sector": "情報・通信",
        "industry": "IT",
        "description": "テスト企業",
        "website_url": "https://example.com",
    }
    defaults.update(kwargs)
    m = MagicMock()
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


def _make_document(**kwargs):
    defaults = {
        "id": 1,
        "company_id": 1,
        "title": "2026年3月期 第3四半期決算短信",
        "doc_type": "financial_report",
        "publish_date": "2026-03-06",
        "source_url": "https://example.com/doc.pdf",
    }
    defaults.update(kwargs)
    m = MagicMock()
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


def _make_analysis(**kwargs):
    defaults = {
        "id": 1,
        "document_id": 1,
        "summary": "売上高は前年比10%増の100億円。営業利益は15億円で過去最高を更新。",
        "sentiment_positive": 0.75,
        "sentiment_negative": 0.1,
        "sentiment_neutral": 0.15,
        "key_points": [
            "売上高が前年比10%増",
            "営業利益が過去最高",
            "新規事業が好調",
            "海外売上が30%増加",
            "通期見通しを上方修正",
        ],
    }
    defaults.update(kwargs)
    m = MagicMock()
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


class TestArticleGenerator:
    def setup_method(self):
        self.gen = ArticleGenerator()
        self.company = _make_company()
        self.document = _make_document()
        self.analysis = _make_analysis()

    def test_generate_paid_article(self):
        result = self.gen.generate_analysis_article(
            document=self.document,
            analysis=self.analysis,
            company=self.company,
            free=False,
        )
        assert isinstance(result, ArticleContent)
        assert "テスト株式会社" in result.title
        assert "1234" in result.title
        assert result.price == 500
        assert "<pay>" in result.body_html
        assert "非常にポジティブ" in result.body_html
        assert len(result.hashtags) > 0
        assert "決算" in result.hashtags

    def test_generate_free_article(self):
        result = self.gen.generate_analysis_article(
            document=self.document,
            analysis=self.analysis,
            company=self.company,
            free=True,
        )
        assert result.price == 0
        assert "<pay>" not in result.body_html
        assert "詳細AI分析" in result.body_html

    def test_generate_article_with_youtube_url(self):
        result = self.gen.generate_analysis_article(
            document=self.document,
            analysis=self.analysis,
            company=self.company,
            free=True,
            youtube_url="https://youtube.com/watch?v=test",
        )
        assert "youtube.com" in result.body_html

    def test_generate_negative_sentiment_article(self):
        analysis = _make_analysis(
            sentiment_positive=0.1,
            sentiment_negative=0.75,
            summary="大幅減益。業績が悪化。",
        )
        result = self.gen.generate_analysis_article(
            document=self.document,
            analysis=analysis,
            company=self.company,
        )
        assert "非常にネガティブ" in result.body_html

    def test_generate_daily_summary(self):
        analyses = [
            (self.document, self.analysis, self.company),
            (
                _make_document(id=2, title="決算2"),
                _make_analysis(id=2, document_id=2),
                _make_company(id=2, name="テスト2社", ticker_code="5678"),
            ),
        ]
        result = self.gen.generate_daily_summary(date.today(), analyses)
        assert isinstance(result, ArticleContent)
        assert result.price == 0
        assert "2社" in result.title
        assert "テスト株式会社" in result.body_html
        assert "テスト2社" in result.body_html

    def test_generate_hashtags(self):
        tags = self.gen._generate_hashtags(self.company)
        assert "決算" in tags
        assert "テスト株式会社" in tags
        assert "1234" in tags
        assert len(tags) <= 8
